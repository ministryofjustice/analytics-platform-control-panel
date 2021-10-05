import logging

from asgiref.sync import async_to_sync
from controlpanel.api import cluster
from controlpanel.api.models import Tool, ToolDeployment
from controlpanel.frontend.consumers import start_background_task
from controlpanel.oidc import OIDCLoginRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic.base import RedirectView
from django.views.generic.list import ListView
from kubernetes.client.rest import ApiException
from rules.contrib.views import PermissionRequiredMixin

log = logging.getLogger(__name__)


class ToolList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = "tools"
    model = Tool
    permission_required = "api.list_tool"
    template_name = "tool-list.html"

    def get_queryset(self):
        """
        Return a queryset for Tool objects where:

        * The tool is to be run on this version of the infrastructure.

        AND EITHER:

        * The tool is not in beta,

        OR

        * The current user is in the beta tester group for the tool.
        """
        if settings.EKS:
            qs = Tool.objects.filter(target_infrastructure=Tool.EKS)
        else:
            qs = Tool.objects.filter(target_infrastructure=Tool.OLD)
        return qs.filter(
            Q(is_restricted=False) |
            Q(target_users=self.request.user.id)
        )

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
        # Defines how a matching chart name is put into a named tool bucket.
        # E.g. jupyter-* charts all end up in the jupyter-lab bucket.
        # chart name match: tool bucket
        tool_chart_lookup = {
            "airflow": "airflow-sqlite",
            "jupyter": "jupyter-lab",
            "rstudio": "rstudio",
        }
        # Arrange tools information
        context["tools_info"] = {}
        for tool in context["tools"]:
            chart_name = tool.chart_name
            # Work out which bucket the chart should be in (it'll be one of
            # those defined in 
            tool_bucket = ""
            for key, bucket_name in tool_chart_lookup.items():
                if key in chart_name:
                    tool_bucket = bucket_name
                    break
            if not tool_bucket:
                # No matching tool bucket for the given chart. So ignore.
                break
            if tool_bucket not in context["tools_info"]:
                context["tools_info"][tool_bucket] = {
                    "name": tool.name,
                    "url": tool.url(user),
                    "deployment": None,
                    "versions": {},
                }

            if chart_name in deployed_chart_names:
                context["tools_info"][tool_bucket]["deployment"] = ToolDeployment(
                    tool, user
                )
            # Each version now needs to display the chart_name and the
            # "app_version" metadata from helm. TODO: Stop using helm.
            context["tools_info"][tool_bucket]["versions"][
                tool.version
            ] = {
                "chart_name": chart_name,
                "description": tool.app_version
            }

        return context


class DeployTool(OIDCLoginRequiredMixin, RedirectView):
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


class RestartTool(OIDCLoginRequiredMixin, RedirectView):
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
