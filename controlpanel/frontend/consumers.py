import asyncio
from datetime import datetime
import json
import logging
from time import sleep
import uuid

from asgiref.sync import async_to_sync
from channels.consumer import SyncConsumer
from channels.layers import get_channel_layer
from django.conf import settings
from django.urls import reverse

from controlpanel.api.helm import HelmError
from controlpanel.api.models import User
from controlpanel.api.tools import Tool
from controlpanel.utils import PatchedAsyncHttpConsumer, sanitize_dns_label


channel_layer = get_channel_layer()

log = logging.getLogger(__name__)


class SSEConsumer(PatchedAsyncHttpConsumer):
    """
    Server Sent Events filtered by the request user's id - so a user only
    receives SSEs intended for them and not any other user.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.streaming = False

    async def handle(self, body):
        """
        Start an event-stream response to the HTTP request (eg: GET /events/)
        """
        self.streaming = True

        await self.send_headers(headers=[
            (b"Cache-Control", b"no-cache"),
            (b"Content-Type", b"text/event-stream"),
            (b"Transfer-Encoding", b"chunked"),
        ])

        # headers are not sent until some part of the body is sent, so send an
        # empty string to force them
        await self.send_body(b'', more_body=True)

        # schedule a coroutine to send keepalive updates
        asyncio.get_event_loop().create_task(self.stream())

        # listen for messages for the current request user only
        group = sanitize_dns_label(self.scope.get("user").auth0_id)
        await self.channel_layer.group_add(group, self.channel_name)

    async def stream(self):
        """
        Send a keepalive message every minute to prevent timeouts
        """
        while self.streaming:
            await self.sse_event({
                "event": "keepalive",
                "data": datetime.now().isoformat(),
            })
            await asyncio.sleep(60)

    async def sse_event(self, event):
        """
        Receive messages with {'type': 'sse.event'} and send as an SSE to the
        client
        """
        payload = "\n".join(f"{key}: {value}" for key, value in event.items())

        await self.send_body(
            f"{payload}\n\n".encode("utf-8"),
            more_body=self.streaming,
        )

    async def disconnect(self):
        """
        Stop the coroutine running on client disconnect
        """
        self.streaming = False

        # leave the group
        group = sanitize_dns_label(self.scope.get("user").auth0_id)
        await self.channel_layer.group_discard(group, self.channel_name)


class BackgroundTaskConsumer(SyncConsumer):

    def tool_deploy(self, message):
        """
        Deploy the named tool for the specified user
        Expects a message with `tool_name` and `user_id` values, eg:
        message = {'tool_name': 'rstudio', 'user_id': 'github|1234'}
        """
        tool = Tool.create(message['tool_name'])
        user = User.objects.get(auth0_id=message['user_id'])

        send_tool_status_update(user.auth0_id, tool.name, 'Deploying...')

        try:
            deploy = tool.deploy_for(user)

        except HelmError as err:
            send_tool_status_update(user.auth0_id, tool.name, f"Error: {str(err)}")
            raise err

        while deploy.poll() is None:
            send_tool_status_update(user.auth0_id, tool.name, "Deploying...")
            sleep(1)

        if deploy.returncode:
            err_msg = deploy.stderr.read()
            send_tool_status_update(user.auth0_id, tool.name, err_msg)
            log.error(err_msg)
            return

        send_tool_status_update(user.auth0_id, tool.name, "Ready")

    def tool_restart(self, message):
        tool = Tool.create(message['tool_name'])
        user = User.objects.get(auth0_id=message['user_id'])

        send_tool_status_update(user.auth0_id, tool.name, "Restarting...")

        tool.restart_for(user)


def send_sse(user_id, event):
    """
    Tell the SSEConsumer to send an event to the specified user
    """
    async_to_sync(channel_layer.group_send)(
        sanitize_dns_label(user_id),
        {
            "type": "sse.event",
            **event
        },
    )


def send_tool_status_update(user_id, tool_name, status):
    """
    Convenience function for sending SSE tool updates
    """
    send_sse(
        user_id,
        {
            "event": "toolStatusChange",
            "data": json.dumps({
                'toolName': tool_name,
                'status': status,
            }),
        },
    )

