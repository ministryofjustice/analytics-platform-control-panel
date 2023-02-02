# Third-party
from django.db import models
from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.validators import validate_ip_ranges


class IPAllowlist(TimeStampedModel):
    """
    Represents a named set of IP ranges.
    An App can be associated with any number of IPAllowlists.
    Access to an App is only possible from the IP ranges specified in the App's
    associated IPAllowlists.
    """

    name = models.CharField(max_length=60, blank=False, unique=True)
    description = models.CharField(max_length=60, blank=True)
    contact = models.CharField(max_length=60, blank=True)
    allowed_ip_ranges = models.TextField(blank=False, validators=[validate_ip_ranges])
    is_recommended = models.BooleanField(default=False)
    history = HistoricalRecords(table_name="control_panel_api_ip_allowlist_history")

    class Meta:
        db_table = "control_panel_api_ip_allowlist"
        ordering = ("name",)

    def __repr__(self):
        return f"<IPAllowlist: {self.pk}|{self.name}>"

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        """
        Save the IP allowlist and then update the allowed IP ranges entry in AWS
        Secrets Manager for all associated apps.
        """
        super().save(*args, **kwargs)
        for app in self.apps.all():
            cluster.App(app).create_or_update_secret(
                {"allowed_ip_ranges": app.app_allowed_ip_ranges}
            )
        return self

    def delete(self, *args, **kwargs):
        """
        Remove this IP allowlist from all associated apps, then delete the IP allowlist.
        This triggers an update to each app's AWS Secrets Manager entry.
        (Deleting the IPAllowlist doesn't trigger the m2m_changed signal in the App
        model because of https://code.djangoproject.com/ticket/17688, so we have to
        remove this IPAllowlist from the Apps that use it first.)
        """
        for app in self.apps.all():
            app.ip_allowlists.remove(self)
        super().delete(*args, **kwargs)
