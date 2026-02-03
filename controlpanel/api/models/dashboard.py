# Third-party
import sentry_sdk
from django.conf import settings
from django.db import models
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api.aws import AWSQuicksight, arn
from controlpanel.api.exceptions import DeleteCustomerError
from controlpanel.api.models.dashboard_viewer import DashboardViewer
from controlpanel.utils import GovukNotifyEmailError, govuk_notify_send_email


class DashboardAdminAccess(TimeStampedModel):
    dashboard = models.ForeignKey("Dashboard", on_delete=models.CASCADE)
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    added_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, related_name="dashboard_admins_added_set"
    )

    class Meta:
        db_table = "control_panel_api_dashboard_admin_access"


class DashboardViewerAccess(TimeStampedModel):
    dashboard = models.ForeignKey("Dashboard", on_delete=models.CASCADE)
    viewer = models.ForeignKey("DashboardViewer", on_delete=models.CASCADE)
    shared_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, related_name="dashboard_viewers_shared_set"
    )

    class Meta:
        db_table = "control_panel_api_dashboard_viewer_access"


class DashboardDomainAccess(TimeStampedModel):
    dashboard = models.ForeignKey("Dashboard", on_delete=models.CASCADE)
    domain = models.ForeignKey("DashboardDomain", on_delete=models.CASCADE)
    added_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, related_name="dashboard_domains_added_set"
    )

    class Meta:
        db_table = "control_panel_api_dashboard_domain_access"


class Dashboard(TimeStampedModel):

    name = models.CharField(max_length=100, blank=False, unique=True)
    description = models.TextField(blank=True)
    quicksight_id = models.CharField(max_length=100, blank=False, unique=True)
    created_by = models.ForeignKey("User", on_delete=models.SET_NULL, null=True)
    admins = models.ManyToManyField(
        "User",
        related_name="dashboards",
        through=DashboardAdminAccess,
        through_fields=("dashboard", "user"),
    )
    viewers = models.ManyToManyField(
        "DashboardViewer",
        related_name="dashboards",
        through=DashboardViewerAccess,
        through_fields=("dashboard", "viewer"),
    )
    whitelist_domains = models.ManyToManyField(
        "DashboardDomain",
        related_name="dashboards",
        through=DashboardDomainAccess,
        through_fields=("dashboard", "domain"),
    )

    class Meta:
        db_table = "control_panel_api_dashboard"

    def get_absolute_url(self, viewname="manage-dashboard-sharing", **kwargs):
        return reverse(viewname, kwargs={"pk": self.pk, **kwargs})

    def get_absolute_add_viewers_url(self):
        return self.get_absolute_url(viewname="dashboard-customers", page_no=1)

    def get_absolute_delete_url(self):
        return self.get_absolute_url(viewname="delete-dashboard")

    def get_absolute_add_admins_url(self):
        return self.get_absolute_url(viewname="add-dashboard-admin")

    def get_absolute_grant_domain_url(self):
        return self.get_absolute_url(viewname="grant-domain-access")

    def get_absolute_change_description_url(self):
        return self.get_absolute_url(viewname="update-dashboard-description")

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

    def add_customers(self, emails, shared_by):
        """
        Add viewers to the dashboard and notify them.

        Args:
            emails: List of email addresses to add as viewers.
            shared_by: User object representing who shared the dashboard.

        Returns:
            List of emails that could not be notified.
        """
        not_notified = []
        inviter_email = (
            shared_by.justice_email.lower() if shared_by and shared_by.justice_email else None
        )
        for email in emails:
            viewer, _ = DashboardViewer.objects.get_or_create(email=email.lower())
            DashboardViewerAccess.objects.get_or_create(
                dashboard=self,
                viewer=viewer,
                defaults={"shared_by": shared_by},
            )

            try:
                govuk_notify_send_email(
                    email_address=email,
                    template_id=settings.NOTIFY_DASHBOARD_ACCESS_TEMPLATE_ID,
                    personalisation={
                        "dashboard": self.name,
                        "dashboard_link": self.url,
                        "dashboard_home": settings.DASHBOARD_SERVICE_URL,
                        "dashboard_admin": inviter_email,
                        "dashboard_description": self.description,
                    },
                )
            except GovukNotifyEmailError:
                not_notified.append(email)

        return not_notified

    def delete_viewers(self, viewers, admin):
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
                    "revoked_by": admin.justice_email,
                },
            )

    def delete_customers_by_id(self, ids, admin):
        viewers = DashboardViewer.objects.filter(pk__in=ids)
        if not viewers:
            raise DeleteCustomerError(f"Customers with IDs {ids} not found.")

        self.delete_viewers(viewers, admin=admin)
        return viewers

    def delete_customer_by_email(self, email, admin):
        viewers = DashboardViewer.objects.filter(email=email)
        if not viewers:
            raise DeleteCustomerError(f"Customer with email {email} not found.")

        self.delete_viewers(viewers, admin=admin)

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
