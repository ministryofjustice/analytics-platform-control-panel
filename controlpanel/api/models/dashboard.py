# Third-party
import sentry_sdk
from django.conf import settings
from django.db import models
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api.aws import AWSQuicksight, arn
from controlpanel.api.exceptions import DeleteCustomerError
from controlpanel.api.models.dashboard_viewer import DashboardViewer
from controlpanel.utils import GovukNotifyEmailError, govuk_notify_send_email


class Dashboard(TimeStampedModel):

    name = models.CharField(max_length=100, blank=False, unique=True)
    quicksight_id = models.CharField(max_length=100, blank=False, unique=True)
    created_by = models.ForeignKey("User", on_delete=models.SET_NULL, null=True)
    admins = models.ManyToManyField("User", related_name="dashboards")
    viewers = models.ManyToManyField("DashboardViewer", related_name="dashboards")
    whitelist_domains = models.ManyToManyField("DashboardDomain", related_name="dashboards")

    class Meta:
        db_table = "control_panel_api_dashboard"

    @property
    def url(self):
        return f"{settings.DASHBOARD_SERVICE_URL}{self.quicksight_id}"

    @property
    def arn(self):
        dashboard_arn = arn(
            "quicksight",
            "dashboard",
            settings.QUICKSIGHT_ACCOUNT_REGION,
            settings.QUICKSIGHT_ACCOUNT_ID,
        )
        return f"{dashboard_arn}/{self.quicksight_id}"

    def is_admin(self, user):
        return self.admins.filter(pk=user.pk).exists()

    def add_customers(self, emails, inviter_email):
        not_notified = []
        for email in emails:
            viewer, _ = DashboardViewer.objects.get_or_create(email=email.lower())
            self.viewers.add(viewer)

            try:
                govuk_notify_send_email(
                    email_address=email,
                    template_id=settings.NOTIFY_DASHBOARD_ACCESS_TEMPLATE_ID,
                    personalisation={
                        "dashboard": self.name,
                        "dashboard_link": self.url,
                        "dashboard_home": settings.DASHBOARD_SERVICE_URL,
                        "dashboard_admin": inviter_email,
                    },
                )
            except GovukNotifyEmailError:
                not_notified.append(email)

        return not_notified

    def delete_viewers(self, viewers):
        """
        Remove the given viewers from the dashboard.
        """
        emails = [viewer.email for viewer in viewers]
        self.viewers.remove(*viewers)

        for email in emails:
            govuk_notify_send_email(
                email_address=email,
                template_id=settings.NOTIFY_DASHBOARD_REVOKED_TEMPLATE_ID,
                personalisation={
                    "dashboard": self.name,
                    "dashboard_link": self.url,
                    "dashboard_home": settings.DASHBOARD_SERVICE_URL,
                },
            )

    def delete_customers_by_id(self, ids):
        viewers = DashboardViewer.objects.filter(pk__in=ids)
        if not viewers:
            raise DeleteCustomerError(f"Customers with IDs {ids} not found.")

        self.delete_viewers(viewers)

    def delete_customer_by_email(self, email):
        viewers = DashboardViewer.objects.filter(email=email)
        if not viewers:
            raise DeleteCustomerError(f"Customer with email {email} not found.")

        self.delete_viewers(viewers)

    def get_embed_url(self):
        """
        Get the QuickSight embed URL for the dashboard.
        """
        assume_role_name = settings.QUICKSIGHT_ASSUMED_ROLE
        quicksight_region = settings.QUICKSIGHT_ACCOUNT_REGION
        quicksight_client = AWSQuicksight(
            assume_role_name=assume_role_name,
            profile_name="control_panel_api",
            region_name=quicksight_region,
        )

        response = quicksight_client.generate_embed_url_for_anonymous_user(
            dashboard_arn=self.arn, dashboard_id=self.quicksight_id
        )

        return response
