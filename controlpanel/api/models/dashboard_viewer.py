# Third-party
from django.db import models
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api import auth0
from controlpanel.api.exceptions import AddViewerError, DeleteViewerError


class DashboardViewer(TimeStampedModel):
    """
    This model is used to store internal and external users who have access
    to a given dashboard.
    """

    email = models.EmailField(blank=False, unique=True)

    class Meta:
        db_table = "control_panel_api_dashboard_viewer"

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.add_viewer(self.email)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.remove_viewer(self.email)
        return super().delete(*args, **kwargs)

    def add_viewer(self, email, env_name=None):
        try:
            auth0.ExtendedAuth0().add_dashboard_member_by_email(
                email=email,
                user_options={"connection": "email"},
            )
        except auth0.Auth0Error as e:
            raise AddViewerError from e

    def remove_viewer(self, email):
        try:
            auth0.ExtendedAuth0().remove_dashboard_role(
                email=email,
            )
        except auth0.Auth0Error as e:
            raise DeleteViewerError from e
