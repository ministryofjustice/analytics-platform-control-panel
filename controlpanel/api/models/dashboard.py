# Third-party
from django.conf import settings
from django.db import models
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api import aws
from controlpanel.api.exceptions import DeleteCustomerError
from controlpanel.api.models.dashboard_viewer import DashboardViewer


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
        arn = aws.arn(
            "quicksight",
            "dashboard",
            settings.QUICKSIGHT_ACCOUNT_REGION,
            settings.QUICKSIGHT_ACCOUNT_ID,
        )
        return f"{arn}/{self.quicksight_id}"

    def is_admin(self, user):
        return self.admins.filter(pk=user.pk).exists()

    def add_customers(self, emails):
        for email in emails:
            viewer, _ = DashboardViewer.objects.get_or_create(email=email)
            self.viewers.add(viewer)

    def delete_customers_by_id(self, customer_ids):
        try:
            viewers = DashboardViewer.objects.filter(pk__in=customer_ids).all()
            self.viewers.remove(*viewers)
        except Exception as e:
            raise DeleteCustomerError from e

    def delete_customer_by_email(self, customer_email):
        try:
            viewer = DashboardViewer.objects.filter(email=customer_email).first()
            self.viewers.remove(viewer)
        except Exception as e:
            raise DeleteCustomerError from e
