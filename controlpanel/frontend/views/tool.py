# Standard library
from urllib.parse import urlencode

# Third-party
import structlog
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.models import Tool, ToolDeployment
from controlpanel.frontend.forms import ToolDeploymentForm
from controlpanel.oidc import OIDCLoginRequiredMixin
from controlpanel.utils import start_background_task

log = structlog.getLogger(__name__)


class ToolList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = "tools"
    model = Tool
    permission_required = "api.list_tool"
    template_name = "tool-list.html"

    def get_queryset(self):
        """
        Return a queryset for Tool objects where:

        * The tool is not retired

        AND EITHER:

        * The tool is not restricted

        OR

        * The current user has access to the restricted tool
        """
        return Tool.objects.exclude(is_retired=True).filter(
            Q(is_restricted=False) | Q(target_users=self.request.user.id)
        )

    # def _add_deployed_charts_info(self, tools_info, user, id_token):
    #     # TODO this is left in place simply to determine the status of a tool. Not sure if it is
    #     # necessary or worth it  we could store the status of the tool on the ToolDeployment model
    #     # instead
    #     deployments = cluster.ToolDeployment.get_deployments(user, id_token)
    #     # build an index using the chart name as the key for easy lookup later
    #     deployments = {deployment.metadata.labels["app"]: deployment for deployment in deployments}  # noqa
    #     for tool_deployment in user.tool_deployments.active():
    #         deployment = deployments.get(tool_deployment.tool.chart_name)
    #         tool = tool_deployment.tool
    #         tools_info[tool_deployment.tool_type]["deployment"] = {
    #             "tool_id": tool.id,
    #             "chart_name": tool.chart_name,
    #             "chart_version": tool.version,
    #             "image_tag": tool.image_tag,
    #             "description": tool.description,
    #             "status": tool_deployment.get_status(id_token=id_token, deployment=deployment),
    #             "is_deprecated": tool.is_deprecated,
    #             "deprecated_message": tool.get_deprecated_message,
    #             "is_retired": tool.is_retired,
    #         }

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
                   "deployment": {
                       "chart_name": "rstudio",
                       "description": "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10",  # noqa: E501
                       "image_tag": "4.0.5",
                       "chart_version": <chart_version>,
                       "tool_id": <id of the tool in table>,
                       "status": <current status of the deployed tool,
                   },
                   "releases": {
                       "<tool_id>": {
                           "chart_name": "rstudio",
                           "description": "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10",  # noqa: E501
                           "image_tag": "4.0.5",
                           "chart_version": <chart_version>,
                           "tool_id": <id of the tool in table>
                       },
                    }
               },
               # ...
           }
        }
        ```
        """
        context = super().get_context_data(*args, **kwargs)
        context["user_guidance_base_url"] = settings.USER_GUIDANCE_BASE_URL
        context["aws_service_url"] = settings.AWS_SERVICE_URL
        context["managed_airflow_dev_url"] = self.build_airflow_url("dev")
        context["managed_airflow_prod_url"] = self.build_airflow_url("prod")
        context["tool_forms"] = [
            self.get_tool_release_form(tool_type=tool_type) for tool_type in ToolDeployment.ToolType
        ]

        return context

    def get_tool_release_form(self, tool_type):
        deployment = self.request.user.tool_deployments.filter(tool_type=tool_type).active().first()
        return ToolDeploymentForm(
            user=self.request.user,
            tool_type=tool_type,
            deployment=deployment,
        )

    def build_airflow_url(self, environment):
        destination = f"mwaa/home?region={settings.AIRFLOW_REGION}#/environments/{environment}/sso"
        args = urlencode(
            {
                "destination": destination,  # noqa: E501
            }
        )
        return f"{settings.AWS_SERVICE_URL}/?{args}"


class RestartTool(OIDCLoginRequiredMixin, RedirectView):
    http_method_names = ["post"]
    url = reverse_lazy("list-tools")

    def get_redirect_url(self, *args, **kwargs):
        """
        So backwards, it's forwards.

        The "name" of the chart to restart is set in the template for
        list-tools, if there's a live deployment.

        That's numberwang.
        """
        name = self.kwargs["name"]

        start_background_task(
            "tool.restart",
            {
                "tool_name": name,
                "tool_id": self.kwargs["tool_id"],
                "user_id": self.request.user.id,
                "id_token": self.request.user.get_id_token(),
            },
        )

        messages.success(
            self.request,
            f"Restarting {name}...",
        )
        return super().get_redirect_url(*args, **kwargs)
