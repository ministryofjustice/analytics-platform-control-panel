from django.db import models
from django_extensions.db.models import TimeStampedModel


class AppIPAllowlist(TimeStampedModel):
    app = models.ForeignKey("App", related_name="apps", on_delete=models.CASCADE)
    ip_allowlist = models.ForeignKey("IPAllowlist", related_name="ip_allowlists", on_delete=models.CASCADE)

    class Meta:
        db_table = "control_panel_api_app_ip_allowlist"
        unique_together = ("app", "ip_allowlist")
        ordering = ("id",)

    def __repr__(self):
        return f"<AppIPAllowlist: {self.pk}|app={self.app} ip_allowlist={self.ip_allowlist}>"
