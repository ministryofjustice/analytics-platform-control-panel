import logging
import secrets

from django.conf import settings
from django.contrib.postgres.fields import JSONField
import django.core.exceptions
from django.db import models
from django.db.models import Q
from django_extensions.db.models import TimeStampedModel

from controlpanel.api import cluster


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
        ordering = ('name',)

    def __repr__(self):
        return f'<Tool: {self.chart_name} {self.version}>'

    def url(self, user):
        return f'https://{user.slug}-{self.chart_name}.{settings.TOOLS_DOMAIN}/'


class ToolDeploymentManager:
    """
    Emulates a Django model manager
    """

    def create(self, *args, **kwargs):
        tool_deployment = ToolDeployment(*args, **kwargs)
        tool_deployment.save()
        return tool_deployment

    def filter(self, **kwargs):
        deployed_versions = {}
        user = kwargs.get('user')
        filter = Q(chart_name=None)  # Always False
        for deployment in cluster.list_tool_deployments(user):
            chart_name, version = deployment.metadata.labels["chart"].rsplit("-", 1)
            deployed_versions[chart_name] = version
            filter = filter | (
                Q(chart_name=chart_name)
                # & Q(version=version)
            )

        tools = Tool.objects.filter(filter)
        results = []
        for tool in tools:
            outdated = tool.version != deployed_versions[tool.chart_name]
            tool_deployment = ToolDeployment(tool, user, outdated)
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

    def __init__(self, tool, user, outdated=False):
        self._id_token = None
        self._subprocess = None
        self.tool = tool
        self.user = user
        self.outdated = outdated

    def __repr__(self):
        return f'<ToolDeployment: {self.tool!r} {self.user!r}>'

    def delete(self):
        """
        Remove the release from the cluster
        """
        cluster.delete_tool_deployment(self)

    @property
    def host(self):
        return f'{self.user.slug}-{self.tool.chart_name}.{settings.TOOLS_DOMAIN}'

    def save(self, *args, **kwargs):
        """
        Deploy the tool to the cluster (asynchronous)
        """
        self._id_token = kwargs.get('id_token')
        self._subprocess = cluster.deploy_tool(self.tool, self.user)

    @property
    def status(self):
        """
        Get the current status of the deployment.
        Polls the subprocess if running, otherwise returns idled status.
        """
        if self._subprocess:
            # poll subprocess and maybe parse any output to get status
            status = self._poll()
            if status:
                return status

        return cluster.get_tool_deployment_status(
            self,
            id_token=self._id_token,
        )

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

    def restart(self, **kwargs):
        """
        Restart the tool deployment
        """
        self._id_token = kwargs.get('id_token')
        cluster.restart_tool_deployment(
            self,
            id_token=self._id_token,
        )

