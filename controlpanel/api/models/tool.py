import logging
import secrets

from django.conf import settings
from django.contrib.postgres.fields import JSONField
import django.core.exceptions
from django.db import models
from django.db.models import Q
from django_extensions.db.models import TimeStampedModel

from controlpanel.api import cluster
from controlpanel.api.helm import HelmRepository


log = logging.getLogger(__name__)


class Tool(TimeStampedModel):
    """
    Represents a software tool available to users of the platform. An instance
    of Tool is an item in the Software Catalogue - not a user's deployed
    instance of a tool.
    """

    description = models.TextField(blank=True)
    chart_name = models.CharField(max_length=100, blank=False)
    name = models.CharField(max_length=100, blank=False)
    values = JSONField(default=dict)
    version = models.CharField(max_length=100, blank=False)

    class Meta(TimeStampedModel.Meta):
        db_table = "control_panel_api_tool"
        ordering = ("name",)

    def __repr__(self):
        return f"<Tool: {self.chart_name} {self.version}>"

    def url(self, user):
        return f"https://{user.slug}-{self.chart_name}.{settings.TOOLS_DOMAIN}/"

    @property
    def app_version(self):
        """
        Returns the "appVersion" for this tool.

        This is metadata in the helm chart which we use to maintain details
        of the actual tool version (e.g. "RStudio: 1.2.1335+conda, R: 3.5.1, ...")
        as opposed to the chart version.

        Returns None if this information is not available for this tool and
        chart version (e.g. the chart was released before the `appVersion`
        was introduced) or because the chart doesn't exist in the helm
        reporitory.
        """

        return HelmRepository.get_chart_app_version(self.chart_name, self.version)


class ToolDeploymentManager:
    """
    Emulates a Django model manager
    """

    def create(self, *args, **kwargs):
        tool_deployment = ToolDeployment(*args, **kwargs)
        tool_deployment.save()
        return tool_deployment

    def filter(self, **kwargs):
        user = kwargs["user"]
        id_token = kwargs["id_token"]
        filter = Q(chart_name=None)  # Always False
        deployments = cluster.ToolDeployment.get_deployments(user, id_token)
        for deployment in deployments:
            chart_name, _ = deployment.metadata.labels["chart"].rsplit("-", 1)
            filter = filter | (Q(chart_name=chart_name))

        tools = Tool.objects.filter(filter)
        results = []
        for tool in tools:
            tool_deployment = ToolDeployment(tool, user)
            results.append(tool_deployment)
        return results


class ToolDeployment:
    """
    Represents a deployed Tool in the cluster
    """

    DoesNotExist = django.core.exceptions.ObjectDoesNotExist
    Error = cluster.ToolDeploymentError
    MultipleObjectsReturned = django.core.exceptions.MultipleObjectsReturned

    objects = ToolDeploymentManager()

    def __init__(self, tool, user):
        self._subprocess = None
        self.tool = tool
        self.user = user

    def __repr__(self):
        return f"<ToolDeployment: {self.tool!r} {self.user!r}>"

    def get_installed_chart_version(self, id_token):
        """
        Returns the installed chart version for this tool

        Returns None if the chart is not installed for the user
        """

        td = cluster.ToolDeployment(self.user, self.tool)
        return td.get_installed_chart_version(id_token)

    def get_installed_app_version(self, id_token):
        """
        Returns the version of the deployed tool

        NOTE: This is the version coming from the helm
        chart `appVersion` field, **not** the version
        of the chart released in the user namespace.

        e.g. if user has `rstudio-2.2.5` (chart version)
        installed in his namespace, this would return
        "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"
        **not** "2.2.5".

        Also bear in mind that Helm added this `appVersion`
        field only "recently" so if a user has an old
        version of a tool chart installed this would return
        `None` as we can't determine the tool version
        as this information is simply not available
        in the helm repository index.
        """

        chart_version = self.get_installed_chart_version(id_token)
        if chart_version:
            return HelmRepository.get_chart_app_version(
                self.tool.chart_name, chart_version
            )

        return None

    def delete(self, id_token):
        """
        Remove the release from the cluster
        """

        cluster.ToolDeployment(self.user, self.tool).uninstall(id_token)

    @property
    def host(self):
        return f"{self.user.slug}-{self.tool.chart_name}.{settings.TOOLS_DOMAIN}"

    def save(self, *args, **kwargs):
        """
        Deploy the tool to the cluster (asynchronous)
        """

        self._subprocess = cluster.ToolDeployment(self.user, self.tool).install()

    def get_status(self, id_token):
        """
        Get the current status of the deployment.
        Polls the subprocess if running, otherwise returns idled status.
        """
        if self._subprocess:
            # poll subprocess and maybe parse any output to get status
            status = self._poll()
            if status:
                return status

        return cluster.ToolDeployment(self.user, self.tool).get_status(id_token)

    def _poll(self):
        """
        Poll the deployment subprocess for status
        """

        if self._subprocess.poll() is None:
            return cluster.TOOL_DEPLOYING

        if self._subprocess.returncode:
            log.error(self._subprocess.stderr.read().strip())
            return cluster.TOOL_DEPLOY_FAILED

        self._subprocess = None

    @property
    def url(self):
        return f"https://{self.host}/"

    def restart(self, id_token):
        """
        Restart the tool deployment
        """

        cluster.ToolDeployment(self.user, self.tool).restart(id_token)
