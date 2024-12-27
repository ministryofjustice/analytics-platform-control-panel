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
    TOOL_BOX_CHART_LOOKUP = {
        "jupyter": "jupyter-lab",
        "rstudio": "rstudio",
        "vscode": "vscode",
    }
    DEFAULT_DEPRECATED_MESSAGE = "The selected release has been deprecated and will be retired soon. Please update to a more recent version."  # noqa
    JUPYTER_DATASCIENCE_CHART_NAME = "jupyter-lab-datascience-notebook"
    JUPYTER_ALL_SPARK_CHART_NAME = "jupyter-lab-all-spark"
    JUPYTER_LAB_CHART_NAME = "jupyter-lab"
    RSTUDIO_CHART_NAME = "rstudio"
    VSCODE_CHART_NAME = "vscode"
    STATUS_RETIRED = "retired"
    STATUS_DEPRECATED = "deprecated"
    STATUS_ACTIVE = "active"
    STATUS_RESTRICTED = "restricted"

    description = models.TextField(blank=False)
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

    is_deprecated = models.BooleanField(default=False)
    deprecated_message = models.TextField(
        blank=True, help_text="If no message is provided, a default message will be used."
    )
    is_retired = models.BooleanField(default=False)
    image_tag = models.CharField(max_length=100)
    users_deployed = models.ManyToManyField(
        "User", through="ToolDeployment", related_name="deployed_tools"
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

        # TODO description is now required when creating a release, so this is unlikely to be called
        # Consider removing
        if not self.description:
            self.description = helm.get_chart_app_version(self.chart_name, self.version) or ""

        super().save(*args, **kwargs)
        return self

    @property
    def get_deprecated_message(self):
        if not self.is_deprecated:
            return ""

        if self.is_retired:
            return ""

        return self.deprecated_message or self.DEFAULT_DEPRECATED_MESSAGE

    @property
    def image_tag_key(self):
        mapping = {
            self.JUPYTER_DATASCIENCE_CHART_NAME: "jupyter.tag",
            self.JUPYTER_ALL_SPARK_CHART_NAME: "jupyter.tag",
            self.JUPYTER_LAB_CHART_NAME: "jupyterlab.image.tag",
            self.RSTUDIO_CHART_NAME: "rstudio.image.tag",
            self.VSCODE_CHART_NAME: "vscode.image.tag",
        }
        return mapping[self.chart_name]

    @property
    def status(self):
        if self.is_retired:
            return self.STATUS_RETIRED.capitalize()
        if self.is_deprecated:
            return self.STATUS_DEPRECATED.capitalize()
        if self.is_restricted:
            return self.STATUS_RESTRICTED.capitalize()
        return self.STATUS_ACTIVE.capitalize()

    @property
    def status_colour(self):
        mapping = {
            self.STATUS_RETIRED: "red",
            self.STATUS_DEPRECATED: "grey",
            self.STATUS_RESTRICTED: "yellow",
            self.STATUS_ACTIVE: "green",
        }
        return mapping[self.status.lower()]

    @property
    def tool_type(self):
        return self.chart_name.split("-")[0]


class ToolDeploymentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)


class ToolDeployment(TimeStampedModel):
    """
    Represents a deployed Tool in the cluster
    """

    class ToolType(models.TextChoices):
        JUPYTER = "jupyter", "Jupyter"
        RSTUDIO = "rstudio", "RStudio"
        VSCODE = "vscode", "VSCode"

    user = models.ForeignKey(to="User", on_delete=models.CASCADE, related_name="tool_deployments")
    tool = models.ForeignKey(to="Tool", on_delete=models.CASCADE, related_name="tool_deployments")
    tool_type = models.CharField(max_length=100, choices=ToolType.choices)
    is_active = models.BooleanField(default=False)

    Error = cluster.ToolDeploymentError

    objects = ToolDeploymentQuerySet.as_manager()

    class Meta:
        ordering = ["-created"]

    def __init__(self, *args, **kwargs):
        # TODO these may not be necessary but leaving for now
        self._subprocess = None
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<ToolDeployment: {self.tool!r} {self.user!r}>"

    def uninstall(self):
        """
        Remove the release from the cluster
        """
        return cluster.ToolDeployment(tool=self.tool, user=self.user).uninstall()

    def delete(self, *args, **kwargs):
        """
        Remove the release from the cluster
        """
        self.uninstall()
        super().delete(*args, **kwargs)

    @property
    def host(self):
        return f"{self.user.slug}-{self.tool.chart_name}.{settings.TOOLS_DOMAIN}"

    def deploy(self):
        """
        Deploy the tool to the cluster (asynchronous)
        """
        self._subprocess = cluster.ToolDeployment(self.user, self.tool).install()

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
