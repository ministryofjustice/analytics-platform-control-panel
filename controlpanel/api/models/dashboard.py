# Third-party
from django.conf import settings
from django.db import models
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords

# First-party/Local
from controlpanel import utils
from controlpanel.api.aws import AWSQuicksight, arn
from controlpanel.api.models.dashboard_viewer import DashboardViewer


class DashboardAdminAccess(TimeStampedModel):
    dashboard = models.ForeignKey(
        "Dashboard", on_delete=models.CASCADE, related_name="admin_access"
    )
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    added_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, related_name="dashboard_admins_added_set"
    )
    history = HistoricalRecords(table_name="control_panel_api_dashboard_admin_access_history")

    class Meta:
        db_table = "control_panel_api_dashboard_admin_access"
        ordering = ["-created"]
        verbose_name_plural = "dashboard admin access records"


class DashboardViewerAccess(TimeStampedModel):
    dashboard = models.ForeignKey(
        "Dashboard", on_delete=models.CASCADE, related_name="viewer_access"
    )
    viewer = models.ForeignKey("DashboardViewer", on_delete=models.CASCADE)
    shared_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, related_name="dashboard_viewers_shared_set"
    )
    history = HistoricalRecords(table_name="control_panel_api_dashboard_viewer_access_history")

    class Meta:
        db_table = "control_panel_api_dashboard_viewer_access"
        ordering = ["-created"]
        verbose_name_plural = "dashboard viewer access records"


class DashboardDomainAccess(TimeStampedModel):
    dashboard = models.ForeignKey(
        "Dashboard", on_delete=models.CASCADE, related_name="domain_access"
    )
    domain = models.ForeignKey("DashboardDomain", on_delete=models.CASCADE)
    added_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, related_name="dashboard_domains_added_set"
    )
    history = HistoricalRecords(table_name="control_panel_api_dashboard_domain_access_history")

    class Meta:
        db_table = "control_panel_api_dashboard_domain_access"
        ordering = ["-created"]
        verbose_name_plural = "dashboard domain access records"


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
    history = HistoricalRecords(table_name="control_panel_api_dashboard_history")

    class Meta:
        db_table = "control_panel_api_dashboard"

    def __str__(self):
        return self.name

    def get_absolute_url(self, viewname="manage-dashboard-sharing", **kwargs):
        return reverse(viewname, kwargs={"pk": self.pk, **kwargs})

    def get_absolute_add_viewers_url(self):
        return self.get_absolute_url(viewname="add-dashboard-viewers")

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

    def add_viewers(self, emails, shared_by):
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
                utils.govuk_notify_send_email(
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
            except utils.GovukNotifyEmailError:
                not_notified.append(email)

        return not_notified

    def delete_viewers(self, viewers, admin):
        """
        Remove the given viewers from the dashboard.
        """
        emails = [viewer.email for viewer in viewers]
        for viewer in viewers:
            # use delete so that django-simple-history keeps a record of it
            self.viewer_access.get(viewer=viewer).delete()

        for email in emails:
            utils.govuk_notify_send_email(
                email_address=email,
                template_id=settings.NOTIFY_DASHBOARD_REVOKED_TEMPLATE_ID,
                personalisation={
                    "dashboard": self.name,
                    "dashboard_link": self.url,
                    "dashboard_home": settings.DASHBOARD_SERVICE_URL,
                    "revoked_by": admin.justice_email,
                },
            )

    def delete_admin(self, user, admin):
        """
        Remove the given admin from the dashboard and notifies them
        """
        # use delete so that django-simple-history keeps a record of it
        self.admin_access.get(user=user).delete()

        utils.govuk_notify_send_email(
            email_address=user.justice_email,
            template_id=settings.NOTIFY_DASHBOARD_ADMIN_REMOVED_TEMPLATE_ID,
            personalisation={
                "dashboard": self.name,
                "revoked_by": admin.justice_email,
            },
        )

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
