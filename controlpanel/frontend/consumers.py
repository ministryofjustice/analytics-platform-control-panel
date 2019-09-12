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

from controlpanel.api import cluster
from controlpanel.api.cluster import (
    TOOL_DEPLOYING,
    TOOL_DEPLOY_FAILED,
    TOOL_READY,
)
from controlpanel.api.models import Tool, ToolDeployment, User
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

        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.send_response(403, b'Forbidden')
            return

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
        Expects a message with `tool_name`, `version` and `user_id` values
        """

        tool, user = self.get_tool_and_user(message)

        update_tool_status(user, tool, TOOL_DEPLOYING)

        try:
            deployment = ToolDeployment(tool, user)
            deployment.save(id_token=message.get('id_token'))

        except ToolDeployment.Error as err:
            update_tool_status(user, tool, TOOL_DEPLOY_FAILED)
            log.error(err)
            return

        status = wait_for_deployment(user, tool, deployment)

        if status == TOOL_DEPLOY_FAILED:
            log.error(f"Failed deploying {tool.name} for {user}")
        else:
            log.debug(f"Deployed {tool.name} for {user}")

    def tool_upgrade(self, message):
        """
        Upgrade simply means re-installing the helm chart for the tool
        """
        self.tool_deploy(message)

    def tool_restart(self, message):
        """
        Restart the named tool for the specified user
        """
        tool, user = self.get_tool_and_user(message)

        update_tool_status(user, tool, "Restarting")

        deployment = ToolDeployment(tool, user)
        deployment.restart(id_token=message.get('id_token'))

        status = wait_for_deployment(user, tool, deployment)

        if status == TOOL_DEPLOY_FAILED:
            log.error(f"Failed restarting {tool.name} for {user}")
        else:
            log.debug(f"Restarted {tool.name} for {user}")

    def get_tool_and_user(self, message):
        tool = Tool.objects.get(
            chart_name=message['tool_name'],
            # version=message['version'],
        )
        user = User.objects.get(auth0_id=message['user_id'])
        return tool, user


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


def update_tool_status(user, tool, status):
    send_sse(user.auth0_id, {
        "event": "toolStatus",
        "data": json.dumps({
            'toolName': tool.chart_name,
            'version': tool.version,
            'status': status,
        }),
    })


def start_background_task(task, message):
    async_to_sync(channel_layer.send)(
        'background_tasks',
        {
            'type': task,
            **message,
        },
    )


def wait_for_deployment(user, tool, deployment):
    while True:
        status = deployment.status
        update_tool_status(user, tool, status)
        if status in (TOOL_DEPLOY_FAILED, TOOL_READY):
            return status
        sleep(1)

