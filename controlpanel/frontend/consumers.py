import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
from time import sleep
import uuid

from asgiref.sync import async_to_sync
from channels.consumer import SyncConsumer
from channels.layers import get_channel_layer
from django.conf import settings
from django.urls import reverse

from controlpanel.api.cluster import (
    TOOL_DEPLOYING,
    TOOL_DEPLOY_FAILED,
    TOOL_IDLED,
    TOOL_READY,
    TOOL_RESTARTING,
    HOME_RESETTING,
    HOME_RESET_FAILED,
)
from controlpanel.api.models import Tool, ToolDeployment, User, HomeDirectory
from controlpanel.utils import PatchedAsyncHttpConsumer, sanitize_dns_label


WORKER_HEALTH_FILENAME = "/tmp/worker_health.txt"


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

        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.send_response(403, b"Forbidden")
            return

        await self.send_headers(
            headers=[
                (b"Cache-Control", b"no-cache"),
                (b"Content-Type", b"text/event-stream"),
                (b"Transfer-Encoding", b"chunked"),
            ]
        )

        # headers are not sent until some part of the body is sent, so send an
        # empty string to force them
        await self.send_body(b"", more_body=True)

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
            await self.sse_event(
                {"event": "keepalive", "data": datetime.now().isoformat(),}
            )
            await asyncio.sleep(60)

    async def sse_event(self, event):
        """
        Receive messages with {'type': 'sse.event'} and send as an SSE to the
        client
        """
        payload = "\n".join(f"{key}: {value}" for key, value in event.items())

        await self.send_body(
            f"{payload}\n\n".encode("utf-8"), more_body=self.streaming,
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
        id_token = message["id_token"]
        tool_deployment = ToolDeployment(tool, user)

        update_tool_status(tool_deployment, id_token, TOOL_DEPLOYING)
        try:
            tool_deployment.save()
        except ToolDeployment.Error as err:
            update_tool_status(tool_deployment, id_token, TOOL_DEPLOY_FAILED)
            log.error(err)
            return

        status = wait_for_deployment(tool_deployment, id_token)

        if status == TOOL_DEPLOY_FAILED:
            log.error(f"Failed deploying {tool.name} for {user}")
        else:
            log.debug(f"Deployed {tool.name} for {user}")

    def tool_restart(self, message):
        """
        Restart the named tool for the specified user
        """
        tool, user = self.get_tool_and_user(message)
        id_token = message["id_token"]

        tool_deployment = ToolDeployment(tool, user)
        update_tool_status(tool_deployment, id_token, TOOL_RESTARTING)

        tool_deployment.restart(id_token=id_token)

        status = wait_for_deployment(tool_deployment, id_token)

        if status == TOOL_DEPLOY_FAILED:
            log.error(f"Failed restarting {tool.name} for {user}")
        else:
            log.debug(f"Restarted {tool.name} for {user}")

    def get_tool_and_user(self, message):
        tool_args = {"chart_name": message["tool_name"]}
        if "version" in message:
            tool_args["version"] = message["version"]

        # On restart we don't specify the version as it doesn't make
        # sense to do so. As we're now allowing more than one
        # Tool instance for the same chart name this means we have to
        # use `filter().first()` (instead of `.get()`) to avoid getting
        # a Django exception when `get()` finds more than 1 Tool record
        # with the same chart name
        tool = Tool.objects.filter(**tool_args).first()
        if not tool:
            raise Exception(f"no Tool record found for query {tool_args}")
        user = User.objects.get(auth0_id=message["user_id"])
        return tool, user

    def home_reset(self, message):
        """
        Reset the home directory of the specified user.
        """
        user = User.objects.get(auth0_id=message["user_id"])
        home_directory = HomeDirectory(user)
        update_home_status(home_directory, HOME_RESETTING)
        
        home_directory.reset()

        status = wait_for_home_reset(home_directory)

        if status == HOME_RESET_FAILED:
            log.error(f"Failed to reset home directory for user {user}")
        else:
            log.debug(f"Reset home directory for user {user}")

    def workers_health(self, message):
        Path(WORKER_HEALTH_FILENAME).touch()

        log.debug(f"Worker health ping task executed")


def send_sse(user_id, event):
    """
    Tell the SSEConsumer to send an event to the specified user
    """
    async_to_sync(channel_layer.group_send)(
        sanitize_dns_label(user_id), {"type": "sse.event", **event},
    )


def update_tool_status(tool_deployment, id_token, status):
    user = tool_deployment.user
    tool = tool_deployment.tool

    app_version = tool_deployment.get_installed_app_version(id_token)

    payload = {
        "toolName": tool.chart_name,
        "version": tool.version,
        "appVersion": app_version,
        "status": status,
    }
    send_sse(user.auth0_id, {"event": "toolStatus", "data": json.dumps(payload),})


def update_home_status(home_directory, status):
    """
    Update the user with the status of their home directory reset task.
    """
    user = home_directory.user
    send_sse(
        user.auth0_id,
        {
            "event": "homeStatus",
            "data": json.dumps({
                "status": status
            }),
        }
    )


def start_background_task(task, message):
    async_to_sync(channel_layer.send)(
        "background_tasks", {"type": task, **message,},
    )


def wait_for_deployment(tool_deployment, id_token):
    status = TOOL_DEPLOYING
    while status == TOOL_DEPLOYING:
        status = tool_deployment.get_status(id_token)
        update_tool_status(tool_deployment, id_token, status)
        sleep(1)
    return status


def wait_for_home_reset(home_directory):
    """
    Check and report upon the reset of the user's home directory.
    """
    status = HOME_RESETTING
    while status == HOME_RESETTING:
        status = home_directory.get_status()
        update_home_status(home_directory, status)
        sleep(1)
    return status
