import logging

from asgiref.sync import async_to_sync
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
from django.views.generic.list import ListView
from kubernetes.client.rest import ApiException
from rules.contrib.views import PermissionRequiredMixin

from controlpanel.api.models import (
    Tool,
    ToolDeployment,
)
from controlpanel.frontend.consumers import start_background_task


log = logging.getLogger(__name__)


class ToolList(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = 'tools'
    model = Tool
    permission_required = 'api.list_tool'
    template_name = "tool-list.html"

    def get_context_data(self, *args, **kwargs):
        user = self.request.user
        id_token = user.get_id_token()

        tool_deployments = ToolDeployment.objects.filter(
            user=user,
            id_token=id_token,
        )

        context = super().get_context_data(*args, **kwargs)
        context["id_token"] = id_token
        context["deployed_tools"] = {
            tool_deployment.tool: tool_deployment
            for tool_deployment in tool_deployments
        }

        return context


class DeployTool(LoginRequiredMixin, RedirectView):
    http_method_names = ['post']
    url = reverse_lazy("list-tools")

    def get_redirect_url(self, *args, **kwargs):
        name = kwargs['name']

        start_background_task('tool.deploy', {
            'tool_name': name,
            'version': self.request.POST['version'],
            'user_id': self.request.user.id,
            'id_token': self.request.user.get_id_token(),
        })

        messages.success(
            self.request, f"Deploying {name}... this may take several minutes",
        )
        return super().get_redirect_url(*args, **kwargs)


class UpgradeTool(LoginRequiredMixin, RedirectView):
    http_method_names = ['post']
    url = reverse_lazy("list-tools")

    def get_redirect_url(self, *args, **kwargs):
        name = kwargs['name']

        start_background_task('tool.upgrade', {
            'tool_name': name,
            'version': self.request.POST['version'],
            'user_id': self.request.user.id,
            'id_token': self.request.user.get_id_token(),
        })

        messages.success(
            self.request, f"Upgrading {name}... this may take several minutes",
        )
        return super().get_redirect_url(*args, **kwargs)


class RestartTool(LoginRequiredMixin, RedirectView):
    http_method_names = ["post"]
    url = reverse_lazy("list-tools")

    def get_redirect_url(self, *args, **kwargs):
        name = self.kwargs['name']

        start_background_task('tool.restart', {
            'tool_name': name,
            'user_id': self.request.user.id,
            'id_token': self.request.user.get_id_token(),
        })

        messages.success(
            self.request, f"Restarting {name}...",
        )
        return super().get_redirect_url(*args, **kwargs)
