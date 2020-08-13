import logging

from asgiref.sync import async_to_sync
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
from django.views.generic.list import ListView
from kubernetes.client.rest import ApiException
from rules.contrib.views import PermissionRequiredMixin

from controlpanel.api import cluster
from controlpanel.api.models import (
    Tool,
    ToolDeployment,
)
from controlpanel.frontend.consumers import start_background_task


log = logging.getLogger(__name__)


class ToolList(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = "tools"
    model = Tool
    permission_required = "api.list_tool"
    template_name = "tool-list.html"

    def get_context_data(self, *args, **kwargs):
        """
        Retrieve information about tools and arrange them for the
        template to use them when being rendered.

        The `tool_info` dictionary in the contexts contains information
        about the tools, whether they're deployed for the user,
        versions, etc...arranged by `chart_name`.

        For example:

        ```
        {
           "tools_info": {
               "rstudio": {
                   "name": "RStudio",
                   "url: "https://john-rstudio.tools.example.com",
                   "deployment": ToolDeployment(RStudio, John),
                   "versions": {
                       "2.2.5": "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10",
                       "1.0.0": None,
                    }
               },
               # ...
           }
        }
        ```
        """

        user = self.request.user
        id_token = user.get_id_token()

        context = super().get_context_data(*args, **kwargs)
        context["id_token"] = id_token

        # Get list of deployed tools
        deployments = cluster.ToolDeployment.get_deployments(user, id_token)
        deployed_chart_names = []
        for deployment in deployments:
            chart_name, _ = deployment.metadata.labels["chart"].rsplit("-", 1)
            deployed_chart_names.append(chart_name)

        # Arrange tools information
        context["tools_info"] = {}
        for tool in context["tools"]:
            chart_name = tool.chart_name
            if chart_name not in context["tools_info"]:
                context["tools_info"][chart_name] = {
                    "name": tool.name,
                    "url": tool.url(user),
                    "deployment": None,
                    "versions": {},
                }

            if chart_name in deployed_chart_names:
                context["tools_info"][chart_name]["deployment"] = ToolDeployment(
                    tool, user
                )

            context["tools_info"][chart_name]["versions"][
                tool.version
            ] = tool.app_version

        return context


class DeployTool(LoginRequiredMixin, RedirectView):
    http_method_names = ["post"]
    url = reverse_lazy("list-tools")

    def get_redirect_url(self, *args, **kwargs):
        name = kwargs["name"]

        start_background_task(
            "tool.deploy",
            {
                "tool_name": name,
                "version": self.request.POST["version"],
                "user_id": self.request.user.id,
                "id_token": self.request.user.get_id_token(),
            },
        )

        messages.success(
            self.request, f"Deploying {name}... this may take several minutes",
        )
        return super().get_redirect_url(*args, **kwargs)


class RestartTool(LoginRequiredMixin, RedirectView):
    http_method_names = ["post"]
    url = reverse_lazy("list-tools")

    def get_redirect_url(self, *args, **kwargs):
        name = self.kwargs["name"]

        start_background_task(
            "tool.restart",
            {
                "tool_name": name,
                "user_id": self.request.user.id,
                "id_token": self.request.user.get_id_token(),
            },
        )

        messages.success(
            self.request, f"Restarting {name}...",
        )
        return super().get_redirect_url(*args, **kwargs)
