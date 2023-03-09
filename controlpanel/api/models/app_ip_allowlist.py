# Third-party
from django.db import models

# First-party/Local
from controlpanel.api import cluster


class AppIPAllowListManager(models.Manager):
    def update_records(self, app, env_name, ip_allowlists):
        for related_item in app.appipallowlists.filter(deployment_env=env_name):
            related_item.delete()
        for ip_range_item in ip_allowlists:
            AppIPAllowList.objects.create(
                app_id=app.id, ip_allowlist_id=ip_range_item.id, deployment_env=env_name
            )

    def update_ip_allowlist(self, *args, **kwargs):
        app = kwargs.get("app")
        github_api_token = kwargs.get("github_api_token")
        env_name = kwargs.get("env_name")
        ip_allowlists = kwargs.get("ip_allowlists")
        self.update_records(app, env_name, ip_allowlists)

        cluster.App(app).create_or_update_secret(
            github_token=github_api_token,
            env_name=env_name,
            secret_key=cluster.App.IP_RANGES,
            secret_value=app.env_allowed_ip_ranges(env_name=env_name),
        )


class AppIPAllowList(models.Model):
    """
    Abstract model for storing the app's allowed ip_ranges under different env.

    These models will be associated with an app and list of ip_range names for each env
    """

    app = models.ForeignKey(
        "App",
        related_name="appipallowlists",
        on_delete=models.CASCADE,
    )

    ip_allowlist = models.ForeignKey(
        "IPAllowlist",
        related_name="appipallowlists",
        on_delete=models.CASCADE,
    )

    deployment_env = models.CharField(max_length=100, blank=False)

    objects = AppIPAllowListManager()

    class Meta:
        db_table = "control_panel_api_app_ip_allowlists"
