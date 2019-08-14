import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
from django.views.generic.list import ListView
from django_eventstream import send_event
from kubernetes.client.rest import ApiException

from controlpanel.api.tools import (
    SUPPORTED_TOOL_NAMES,
    Tool,
    ToolDeployment,
    ToolDeploymentError,
)


channel_layer = get_channel_layer()
log = logging.getLogger(__name__)


class ToolsList(LoginRequiredMixin, ListView):
    context_object_name = 'tools'
    template_name = "tools.html"

    def get_queryset(self):
        try:
            deployed_tools = ToolDeployment.list(self.request.user)
        except ApiException as e:
            log.warn(e)
            return []
        deployable_tools = list(SUPPORTED_TOOL_NAMES)
        for tool in deployed_tools:
            if tool.name in deployable_tools:
                deployable_tools.remove(tool.name)
        deployable_tools = [
            {"name": name}
            for name in deployable_tools
        ]

        return [
            *deployed_tools,
            *deployable_tools,
        ]


class DeployTool(LoginRequiredMixin, RedirectView):
    http_method_names = ['post']
    url = reverse_lazy("list-tools")

    def get_redirect_url(self, *args, **kwargs):
        name = self.kwargs["name"]

        try:
            Tool.create(name).deploy_for(self.request.user)

        except ToolDeploymentError as error:
            messages.error(f"Failed deploying {name}")
            log.error(error)

        else:
            messages.success(
                self.request,
                f"Deploying {name}... this may take up to 5 minutes",
            )
        return super().get_redirect_url(*args, **kwargs)


class RestartTool(LoginRequiredMixin, RedirectView):
    http_method_names = ["post"]
    url = reverse_lazy("list-tools")

    def get_redirect_url(self, *args, **kwargs):
        name = self.kwargs['name']

        async_to_sync(channel_layer.send)(
            'tools',
            {
                'type': 'restarttool',
                'tool_name': name,
                'user_id': self.request.user.id,
            },
        )
        send_event(
            'test', 'toolStatusChange', {'toolName': name, 'status': 'Restarting...'},
        )

        messages.success(
            self.request, f"Restarting {name}...",
        )
        return super().get_redirect_url(*args, **kwargs)
