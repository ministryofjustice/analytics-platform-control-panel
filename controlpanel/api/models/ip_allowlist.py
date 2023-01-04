# Third-party
from django.db import models
from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords

# First-party/Local
from controlpanel.api.validators import validate_ip_ranges


class IPAllowlist(TimeStampedModel):
    name = models.CharField(max_length=60, blank=False, unique=True)
    description = models.CharField(max_length=60, blank=True)
    contact = models.CharField(max_length=60, blank=True)
    allowed_ip_ranges = models.TextField(blank=False, validators=[validate_ip_ranges])
    history = HistoricalRecords(table_name="control_panel_api_ip_allowlist_history")

    class Meta:
        db_table = "control_panel_api_ip_allowlist"
        ordering = ("name",)

    def __repr__(self):
        return f"<IPAllowlist: {self.pk}|{self.name}>"

    def __str__(self):
        return f"{self.name}"
