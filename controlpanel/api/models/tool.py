# Third-party
import django.core.exceptions
import structlog
from django.conf import settings
from django.db import models
from django.db.models import JSONField
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api import cluster, helm

log = structlog.getLogger(__name__)


class Tool(TimeStampedModel):
    """
    Represents a software tool available to users of the platform. An instance
    of Tool is an item in the Software Catalogue - not a user's deployed
    instance of a tool.
    """

    # Defines how a matching chart name is put into a named tool bucket.
    # E.g. jupyter-* charts all end up in the jupyter-lab bucket.
    # chart name match: tool bucket
    TOOL_BOX_CHART_LOOKUP = {"jupyter": "jupyter-lab",
                             "rstudio": "rstudio",
                             "visual-studio-code": "visual-studio-code",
                             "vscode": "vscode"}

    description = models.TextField(blank=True)
    chart_name = models.CharField(max_length=100, blank=False)
    name = models.CharField(max_length=100, blank=False)
    values = JSONField(default=dict)
    version = models.CharField(max_length=100, blank=False)
    # The release is restricted to only certain users.
    is_restricted = models.BooleanField(default=False)
    # The users for whom this release is visible
    target_users = models.ManyToManyField("User")

    # If set, the bespoke name for the tool to be used in the domain name
    # (rather than the default chart name).
    tool_domain = models.SlugField(
        help_text=(
            "Name to use in the tool's domain instead of chart name. E.g. "
            'use the standard "jupyter-lab" instead of a custom chart name.'
        ),
        max_length=100,
        blank=True,
        null=True,
        default=None,
    )

    class Meta(TimeStampedModel.Meta):
        db_table = "control_panel_api_tool"
        ordering = ("name",)

    def __repr__(self):
        return f"<Tool: {self.chart_name} {self.version}>"

    def url(self, user):
        tool = self.tool_domain or self.chart_name
        return f"https://{user.slug}-{tool}.{settings.TOOLS_DOMAIN}/"

    def save(self, *args, **kwargs):
        helm.update_helm_repository(force=True)

        if not self.description:
            self.description = (
                helm.get_chart_app_version(self.chart_name, self.version) or ""
            )

        super().save(*args, **kwargs)
        return self

    @property
    def image_tag(self):
        chart_image_key_name = self.chart_name.split("-")[0]
        values = self.values or {}
        return values.get("{}.tag".format(chart_image_key_name)) or values.get(
            "{}.image.tag".format(chart_image_key_name)
        )


class ToolDeploymentManager:
    """
    Emulates a Django model manager
    """

    def create(self, *args, **kwargs):
        tool_deployment = ToolDeployment(*args, **kwargs)
        tool_deployment.save()
        return tool_deployment


class ToolDeployment:
    """
    Represents a deployed Tool in the cluster
    """

    DoesNotExist = django.core.exceptions.ObjectDoesNotExist
    Error = cluster.ToolDeploymentError
    MultipleObjectsReturned = django.core.exceptions.MultipleObjectsReturned

    objects = ToolDeploymentManager()

    def __init__(self, tool, user, old_chart_name=None):
        self._subprocess = None
        self.tool = tool
        self.user = user
        self.old_chart_name = old_chart_name

    def __repr__(self):
        return f"<ToolDeployment: {self.tool!r} {self.user!r}>"

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
        self._subprocess = cluster.ToolDeployment(
            self.user, self.tool, self.old_chart_name
        ).install()

    def get_status(self, id_token, deployment=None):
        """
        Get the current status of the deployment.
        Polls the subprocess if running, otherwise returns idled status.
        """
        if self._subprocess:
            # poll subprocess and maybe parse any output to get status
            log.info("Polling helm subprocess")
            status = self._poll()
            if status:
                log.info(status)
                return status
        return cluster.ToolDeployment(self.user, self.tool).get_status(
            id_token, deployment=deployment
        )

    def _poll(self):
        """
        Poll the deployment subprocess for status
        """
        if self._subprocess.poll() is None:
            return cluster.TOOL_DEPLOYING
        if self._subprocess.returncode:
            log.error(self._subprocess.stdout.read().strip())
            log.error(self._subprocess.stderr.read().strip())
            return cluster.TOOL_DEPLOY_FAILED
        # The process must have finished with a success. Log the output for
        # the sake of visibility.
        log.info(self._subprocess.stdout.read().strip())
        self._subprocess = None

    @property
    def url(self):
        return f"https://{self.host}/"

    def restart(self, id_token):
        """
        Restart the tool deployment
        """
        cluster.ToolDeployment(self.user, self.tool).restart(id_token)


class HomeDirectory:
    """
    Represents a user's home directory in the cluster
    """

    def __init__(self, user):
        self._subprocess = None
        self.user = user

    def __repr__(self):
        return f"<HomeDirectoryManager: {self.user!r}>"

    def reset(self):
        """
        Update the user's home directory (asynchronous).
        """
        self._subprocess = cluster.User(self.user).reset_home()

    def get_status(self):
        """
        Get the current status of the reset.
        Polls the subprocess if running, else returns an "is reset" status.
        """
        if self._subprocess:
            status = self._poll()
            if status:
                return status
        return cluster.HOME_RESET

    def _poll(self):
        """
        Poll the deployment subprocess for status
        """
        if self._subprocess.poll() is None:
            return cluster.HOME_RESETTING
        if self._subprocess.returncode:
            log.error(self._subprocess.stdout.read().strip())
            log.error(self._subprocess.stderr.read().strip())
            return cluster.HOME_RESET_FAILED
        # The process must have finished with a success. Log the output for
        # the sake of visibility.
        log.info(self._subprocess.stdout.read().strip())
        self._subprocess = None
