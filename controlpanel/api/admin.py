# Standard library
import csv

# Third-party
from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import ngettext
from simple_history.admin import SimpleHistoryAdmin

# First-party/Local
from controlpanel.api.models import (
    App,
    DashboardDomain,
    Feedback,
    IPAllowlist,
    JusticeDomain,
    S3Bucket,
    ToolDeployment,
    User,
)
from controlpanel.api.models.dashboard import (
    Dashboard,
    DashboardAdminAccess,
    DashboardDomainAccess,
    DashboardViewerAccess,
)
from controlpanel.api.models.status_post import StatusPageEvent
from controlpanel.api.tasks.user import upgrade_user_helm_chart

# Historical models for browsing audit trail including deletions
HistoricalDashboard = Dashboard.history.model
HistoricalDashboardAdminAccess = DashboardAdminAccess.history.model
HistoricalDashboardViewerAccess = DashboardViewerAccess.history.model
HistoricalDashboardDomainAccess = DashboardDomainAccess.history.model


def make_migration_pending(modeladmin, request, queryset):
    queryset.update(migration_state=User.PENDING)


make_migration_pending.short_description = "Mark selected users as pending migration"


def export_as_csv(filename, row_data):
    """Helper function to export data as CSV and return in HttpResponse."""
    response = HttpResponse(content_type="text/csv")
    timestamp = timezone.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{filename}_{timestamp}.csv"
    response["Content-Disposition"] = f"attachment; filename={filename}"

    # Handle empty data case
    if not row_data:
        writer = csv.DictWriter(response, fieldnames=[])
        writer.writeheader()
        return response

    writer = csv.DictWriter(response, fieldnames=row_data[0].keys())
    writer.writeheader()
    writer.writerows(row_data)
    return response


class AppAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_by", "created")
    list_filter = ("created_by",)
    search_fields = (
        "name",
        "description",
        "slug",
    )


class S3Admin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created", "is_data_warehouse", "is_deleted")
    list_filter = ("created_by", "is_data_warehouse", "is_deleted")
    search_fields = ("name",)


class UserAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "auth0_id",
        "email",
        "justice_email",
        "is_superuser",
        "migration_state",
        "last_login",
    )
    exclude = ("password",)
    list_filter = [
        "migration_state",
        "last_login",
        ("justice_email", admin.EmptyFieldListFilter),
    ]
    search_fields = (
        "username",
        "email",
        "auth0_id",
    )
    actions = [
        "upgrade_bootstrap_user_helm_chart",
        "upgrade_provision_user_helm_chart",
        "reset_home_directory",
        "export_as_csv",
    ]

    def _upgrade_helm_chart(self, request, queryset, chart_name):
        total = 0
        for user in queryset:
            if not user.is_iam_user:
                continue

            upgrade_user_helm_chart.delay(user.username, chart_name)
            total += 1

        self.message_user(
            request,
            ngettext(
                f"{chart_name} helm chart updated for %d user.",
                f"{chart_name} helm chart updated for %d users.",
                total,
            )
            % total,
            messages.SUCCESS,
        )

    @admin.action(description="Upgrade bootstrap-user helm chart")
    def upgrade_bootstrap_user_helm_chart(self, request, queryset):
        self._upgrade_helm_chart(request, queryset, f"{settings.HELM_REPO}/bootstrap-user")

    @admin.action(description="Reset users home directory")
    def reset_home_directory(self, request, queryset):
        self._upgrade_helm_chart(request, queryset, f"{settings.HELM_REPO}/reset-user-efs-home")

    @admin.action(description="Export selected users as CSV")
    def export_as_csv(self, request, queryset):
        data = [
            {
                "username": obj.username,
                "alpha_role_arn": obj.iam_role_name,
                "k8s_namespace": obj.k8s_namespace,
                "email": obj.email,
                "justice_email": obj.justice_email,
                "auth0_id": obj.auth0_id,
                "name": obj.name,
                "azure_oid": obj.azure_oid,
                "date_joined": obj.date_joined,
            }
            for obj in queryset
        ]

        return export_as_csv(filename="users", row_data=data)


class IPAllowlistAdmin(SimpleHistoryAdmin):
    list_display = ("name", "description", "created", "modified")
    history_list_display = ("description", "contact", "allowed_ip_ranges")


class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("satisfaction_rating", "suggestions", "date_added")


class DashboardDomainAdmin(admin.ModelAdmin):
    list_display = ("name",)


class ToolDeploymentAdmin(admin.ModelAdmin):
    list_display = (
        "user__username",
        "tool_type",
        "tool__image_tag",
        "tool__version",
        "tool__description",
        "is_active",
        "created",
    )
    list_filter = [
        "is_active",
        "tool_type",
        "tool__is_retired",
        "tool__is_deprecated",
        "tool__is_restricted",
    ]
    search_fields = ["user__username", "tool__description"]
    actions = ["export_as_csv"]

    @admin.action
    def export_as_csv(self, request, queryset):
        queryset = queryset.select_related("user", "tool")
        data = [
            {
                "username": obj.user.username,
                "tool_type": obj.tool_type,
                "image_tag": obj.tool.image_tag,
                "chart_version": obj.tool.version,
                "description": obj.tool.description,
                "email": obj.user.email,
                "justice_email": obj.user.justice_email,
                "is_active": obj.is_active,
                "is_retired": obj.tool.is_retired,
                "is_deprecated": obj.tool.is_deprecated,
                "created": obj.created,
            }
            for obj in queryset
        ]

        return export_as_csv(filename="tool_deployments", row_data=data)


class JusticeDomainAdmin(admin.ModelAdmin):
    list_display = ("domain",)


class StatusPageEventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "post_type",
        "severity",
        "status",
        "reported_at",
        "starts_at",
        "ends_at",
        "href",
        "modified",
    )
    list_filter = ("post_type", "severity", "status")
    search_fields = ("title", "href")
    ordering = ("-modified",)
    readonly_fields = ("created", "modified", "raw_payload")
    date_hierarchy = "reported_at"


class HistoricalDashboardAccessAdmin(admin.ModelAdmin):
    """Admin for browsing dashboard access history including deletions."""

    list_display = ("id", "dashboard", "history_type", "history_date", "history_user")
    list_filter = ("history_type", "history_date")
    search_fields = ("dashboard__name",)
    ordering = ("-history_date",)
    readonly_fields = (
        "id",
        "dashboard",
        "history_type",
        "history_date",
        "history_user",
        "history_change_reason",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class HistoricalDashboardAdminAccessAdmin(HistoricalDashboardAccessAdmin):
    list_display = (
        "id",
        "dashboard",
        "user",
        "added_by",
        "history_type",
        "history_date",
        "history_user",
    )
    search_fields = (
        "dashboard__name",
        "dashboard__quicksight_id",
        "user__username",
        "added_by__username",
    )
    readonly_fields = HistoricalDashboardAccessAdmin.readonly_fields + ("user", "added_by")


class HistoricalDashboardViewerAccessAdmin(HistoricalDashboardAccessAdmin):
    list_display = (
        "id",
        "dashboard",
        "viewer",
        "shared_by",
        "history_type",
        "history_date",
        "history_user",
    )
    search_fields = (
        "dashboard__name",
        "dashboard__quicksight_id",
        "viewer__email",
        "shared_by__username",
    )
    readonly_fields = HistoricalDashboardAccessAdmin.readonly_fields + ("viewer", "shared_by")


class HistoricalDashboardDomainAccessAdmin(HistoricalDashboardAccessAdmin):
    list_display = (
        "id",
        "dashboard",
        "domain",
        "added_by",
        "history_type",
        "history_date",
        "history_user",
    )
    search_fields = (
        "dashboard__name",
        "dashboard__quicksight_id",
        "domain__name",
        "added_by__username",
    )
    readonly_fields = HistoricalDashboardAccessAdmin.readonly_fields + ("domain", "added_by")


class HistoricalDashboardAdmin(admin.ModelAdmin):
    """Admin for browsing dashboard history including deletions."""

    list_display = (
        "id",
        "name",
        "quicksight_id",
        "created_by",
        "history_type",
        "history_date",
        "history_user",
    )
    list_filter = ("history_type", "history_date")
    search_fields = ("name", "quicksight_id")
    ordering = ("-history_date",)
    readonly_fields = (
        "id",
        "name",
        "description",
        "quicksight_id",
        "created_by",
        "history_type",
        "history_date",
        "history_user",
        "history_change_reason",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(App, AppAdmin)
admin.site.register(S3Bucket, S3Admin)
admin.site.register(User, UserAdmin)
admin.site.register(IPAllowlist, IPAllowlistAdmin)
admin.site.register(Feedback, FeedbackAdmin)
admin.site.register(ToolDeployment, ToolDeploymentAdmin)
admin.site.register(DashboardDomain, DashboardDomainAdmin)
admin.site.register(JusticeDomain, JusticeDomainAdmin)
admin.site.register(StatusPageEvent, StatusPageEventAdmin)
admin.site.register(Dashboard, SimpleHistoryAdmin)
admin.site.register(HistoricalDashboardAdminAccess, HistoricalDashboardAdminAccessAdmin)
admin.site.register(HistoricalDashboardViewerAccess, HistoricalDashboardViewerAccessAdmin)
admin.site.register(HistoricalDashboardDomainAccess, HistoricalDashboardDomainAccessAdmin)
admin.site.register(HistoricalDashboard, HistoricalDashboardAdmin)
