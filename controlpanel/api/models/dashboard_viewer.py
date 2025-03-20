# Third-party
from django.db import models
from django_extensions.db.models import TimeStampedModel


class DashboardViewer(TimeStampedModel):
    """
    This model is used to store internal and external users who have access
    to a given dashboard.
    """

    email = models.EmailField(blank=False, unique=True)

    class Meta:
        db_table = "control_panel_api_dashboard_viewer"
