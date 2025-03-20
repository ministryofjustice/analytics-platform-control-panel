# Third-party
from django.conf import settings
from django.db import models
from django_extensions.db.models import TimeStampedModel


class Dashboard(TimeStampedModel):

    name = models.CharField(max_length=100, blank=False, unique=True)
    quicksight_id = models.CharField(max_length=100, blank=False, unique=True)
    created_by = models.ForeignKey("User", on_delete=models.SET_NULL, null=True)
    admins = models.ManyToManyField("User", related_name="dashboards")
    viewers = models.ManyToManyField("DashboardViewer", related_name="dashboards")
    whitelist_domains = models.ManyToManyField("DashboardDomain", related_name="dashboards")

    class Meta:
        db_table = "control_panel_api_dashboard"

    def get_dashboard_url(self):
        return f"{settings.DASHBOARD_SERVICE_URL}{self.quicksight_id}"
