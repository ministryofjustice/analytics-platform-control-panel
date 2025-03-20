# Third-party
from django.db import models
from django_extensions.db.models import TimeStampedModel


class DashboardDomain(TimeStampedModel):
    """
    This model is used to store domains that can access a dashboard.
    """

    domain_name = models.CharField(max_length=100, blank=False, unique=True)

    class Meta:
        db_table = "control_panel_api_dashboard_domain"
