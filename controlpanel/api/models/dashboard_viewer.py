# Third-party
from django.db import models
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api import auth0
from controlpanel.api.exceptions import AddCustomerError


class DashboardViewer(TimeStampedModel):
    """
    This model is used to store internal and external users who have access
    to a given dashboard.
    """

    email = models.EmailField(blank=False, unique=True)

    class Meta:
        db_table = "control_panel_api_dashboard_viewer"

    def save(self, *args, **kwargs):
        self.add_viewer(self.email)
        return super().save(*args, **kwargs)

    def add_viewer(self, email, env_name=None):
        try:
            auth0.ExtendedAuth0().add_dashboard_member_by_email(
                email=email,
                user_options={"connection": "email"},
            )
        except auth0.Auth0Error as e:
            raise AddCustomerError from e
