import logging
from time import sleep

from channels.consumer import SyncConsumer
from django_eventstream import send_event

from controlpanel.api.helm import HelmError
from controlpanel.api.models import User
from controlpanel.api.tools import Tool


log = logging.getLogger(__name__)


class ToolConsumer(SyncConsumer):

    def deploy_tool(self, message):
        tool = Tool.create(message['tool_name'])
        user = User.objects.get(auth0_id=message['user_id'])

        log.debug(f'deploy_tool({tool.name}, {user.id})')

        try:
            deploy = tool.deploy_for(user)

        except HelmError as err:
            send_tool_status_change(tool.name, str(err))
            log.error(err)

        while deploy.poll() is None:
            sleep(1)

        if deploy.returncode:
            err_msg = deploy.stderr.read()
            send_tool_status_change(tool.name, err_msg)
            log.error(err_msg)
            return

        out = deploy.stdout.read()
        send_tool_status_change(tool.name, out)
        log.debug(out)

    def restart_tool(self, message):
        tool = Tool.create(message['tool_name'])
        user = User.objects.get(auth0_id=message['user_id'])

        log.debug(f'restart_tool({tool.name}, {user.id}')

        tool.restart_for(user)

        send_tool_status_change(tool.name, "Restarting...")


def send_tool_status_change(tool_name, status):
    send_event(
        'test',
        'toolStatusChange',
        {'toolName': tool_name, 'status': status},
    )
