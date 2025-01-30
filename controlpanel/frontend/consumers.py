# Standard library
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from time import sleep

# Third-party
import structlog
from channels.consumer import SyncConsumer
from django.conf import settings
from django.db import transaction

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.cluster import (  # TOOL_IDLED,; TOOL_READY,
    HOME_RESET_FAILED,
    HOME_RESETTING,
    TOOL_DEPLOY_FAILED,
    TOOL_DEPLOYING,
    TOOL_READY,
    TOOL_RESTARTING,
)
from controlpanel.api.models import App, HomeDirectory, IPAllowlist, Tool, ToolDeployment, User
from controlpanel.utils import PatchedAsyncHttpConsumer, sanitize_dns_label, send_sse

log = structlog.getLogger(__name__)


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
        asyncio.get_running_loop().create_task(self.stream())

        # listen for messages for the current request user only
        group = sanitize_dns_label(self.scope.get("user").auth0_id)
        await self.channel_layer.group_add(group, self.channel_name)

    async def stream(self):
        """
        Send a keepalive message every minute to prevent timeouts
        """
        while self.streaming:
            await self.sse_event(
                {
                    "event": "keepalive",
                    "data": datetime.now().isoformat(),
                }
            )
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

        # leave the group if user is logged in.
        user = self.scope.get("user")
        if user.is_authenticated:
            group = sanitize_dns_label(user.auth0_id)
            await self.channel_layer.group_discard(group, self.channel_name)


class BackgroundTaskConsumer(SyncConsumer):
    def app_ip_ranges_update(self, message):
        user = User.objects.get(auth0_id=message["user_id"])
        app = App.objects.get(pk=message["app_id"])

        app_manager_ins = cluster.App(app, user.github_api_token)
        deployment_env_names = app_manager_ins.get_deployment_envs()

        for env_name in deployment_env_names:
            app_manager_ins.create_or_update_secret(
                env_name=env_name,
                secret_key=cluster.App.IP_RANGES,
                secret_value=app.env_allowed_ip_ranges(env_name=env_name),
            )

    def app_ip_ranges_delete(self, message):
        user = User.objects.get(auth0_id=message["user_id"])
        app = App.objects.get(pk=message["app_id"])
        ip_range = IPAllowlist.objects.get(pk=message["ip_range_id"])

        with transaction.atomic():
            app.ip_allowlists.remove(ip_range)

            app_manager_ins = cluster.App(app, user.github_api_token)
            deployment_env_names = app_manager_ins.get_deployment_envs()
            for env_name in deployment_env_names:
                app_manager_ins.create_or_update_secret(
                    env_name=env_name,
                    secret_key=cluster.App.IP_RANGES,
                    secret_value=app.env_allowed_ip_ranges(env_name=env_name),
                )

        # Check whether the ip_range has been used by anywhere,
        # then remove it permanently, race condition?
        if ip_range.apps.count() == 0:
            ip_range.delete()

    def tool_deploy(self, message):
        """
        Uninstall the previous tool deployment, and deploy the new one.
        Expects a message with `previous_deployment_id`, and 'new_deployment_id' values in order
        to identify the user and the tool to deploy.
        """
        # if we have a previous deployment, uninstall it
        previous_deployment = ToolDeployment.objects.filter(
            pk=message["previous_deployment_id"]
        ).first()
        if previous_deployment:
            try:
                previous_deployment.uninstall()
            except ToolDeployment.Error as err:
                # if something went wrong, log the error but continue to try to deploy the new tool
                log.error(err)
                pass
        new_deployment_qs = ToolDeployment.objects.select_for_update().filter(
            pk=message["new_deployment_id"]
        )
        with transaction.atomic():
            new_deployment = new_deployment_qs.get()
            if new_deployment.is_active:
                log.info("Tool deployment already active, ending")
                return
            new_deployment.is_active = True
            new_deployment.save()
            log.info("Tool deployment marked as active")

        # tool = Tool.objects.get(pk=message["new_tool_release_id"])
        # user = User.objects.get(auth0_id=message["user_id"])
        # locked_qs = user.tool_deployments.select_for_update()
        # with transaction.atomic():
        #     new_deployment, created = locked_qs.get_or_create(
        #         tool=tool,
        #         user=user,
        #         is_active=True,
        #         tool_type=tool.tool_type,
        #     )
        #     log.info(f"Tool deployment created: {created}")
        #     if not created:
        #         log.info(f"Tool deployment already exists, ending")
        #         return

        update_tool_status(tool_deployment=new_deployment, status=TOOL_DEPLOYING)
        try:
            log.info(f"New dep subprocess: {new_deployment._subprocess}")
            new_deployment.deploy()
            log.debug(f"Deployed {new_deployment.tool.name} for {new_deployment.user}")
        except ToolDeployment.Error as err:
            # if something went wrong, log the error and unmark the deployment object as active to
            # allow the user to retry deploying the tool
            new_deployment.is_active = False
            new_deployment.save()
            update_tool_status(tool_deployment=new_deployment, status=TOOL_DEPLOY_FAILED)
            self._send_to_sentry(err)
            log.error(err)
            log.warning(f"Failed deploying {new_deployment.tool.name} for {new_deployment.user}")
            return

        status = wait_for_deployment(new_deployment, message["id_token"])
        update_tool_status(tool_deployment=new_deployment, status=status)

    def _send_to_sentry(self, error):
        if os.environ.get("SENTRY_DSN"):
            # Third-party
            import sentry_sdk

            sentry_sdk.capture_exception(error)

    def tool_restart(self, message):
        """
        Restart the named tool for the specified user
        """
        tool_deployment = ToolDeployment.objects.active().get(
            id=message["tool_deployment_id"],
            user=message["user_id"],
        )

        update_tool_status(tool_deployment, TOOL_RESTARTING)
        tool_deployment.restart(id_token=message["id_token"])
        status = wait_for_deployment(tool_deployment, message["id_token"])

        if status == TOOL_DEPLOY_FAILED:
            log.warning(f"Failed restarting {tool_deployment.tool.name} for {tool_deployment.user}")
        else:
            log.debug(f"Restarted {tool_deployment.tool.name} for {tool_deployment.user}")

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
            log.warning(f"Failed to reset home directory for user {user}")
        else:
            log.debug(f"Reset home directory for user {user}")

    def workers_health(self, message):
        Path(settings.WORKER_HEALTH_FILENAME).touch()

        log.debug("Worker health ping task executed")


def update_tool_status(tool_deployment, status):
    user = tool_deployment.user
    tool = tool_deployment.tool

    payload = {
        "toolName": tool.chart_name,
        "version": tool.version,
        "tool_id": tool.id,
        "status": status,
    }
    send_sse(
        user.auth0_id,
        {
            "event": "toolStatus",
            "data": json.dumps(payload),
        },
    )


def update_home_status(home_directory, status):
    """
    Update the user with the status of their home directory reset task.
    """
    user = home_directory.user
    send_sse(
        user.auth0_id,
        {
            "event": "homeStatus",
            "data": json.dumps({"status": status}),
        },
    )


def wait_for_deployment(tool_deployment, id_token):
    status = TOOL_DEPLOYING
    while status == TOOL_DEPLOYING:
        status = tool_deployment.get_status(id_token)
        update_tool_status(tool_deployment, status)
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
