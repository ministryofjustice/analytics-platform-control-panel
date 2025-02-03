# Standard library
import csv

# Third-party
from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from simple_history.admin import SimpleHistoryAdmin

# First-party/Local
from controlpanel.api.models import App, Feedback, IPAllowlist, S3Bucket, ToolDeployment, User


def make_migration_pending(modeladmin, request, queryset):
    queryset.update(migration_state=User.PENDING)


make_migration_pending.short_description = "Mark selected users as pending migration"


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
    actions = [make_migration_pending]
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


class IPAllowlistAdmin(SimpleHistoryAdmin):
    list_display = ("name", "description", "created", "modified")
    history_list_display = ("description", "contact", "allowed_ip_ranges")


class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("satisfaction_rating", "suggestions", "date_added")


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
        response = HttpResponse(content_type="text/csv")
        timestamp = timezone.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{self.model._meta.verbose_name_plural}_{timestamp}.csv"
        response["Content-Disposition"] = f"attachment; filename={filename}"

        fieldnames = [
            "username",
            "tool_type",
            "image_tag",
            "chart_version",
            "description",
            "email",
            "justice_email",
            "is_active",
            "is_retired",
            "is_deprecated",
            "created",
        ]
        writer = csv.DictWriter(response, fieldnames=fieldnames)
        writer.writeheader()

        for obj in queryset:
            writer.writerow(
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
            )

        return response


admin.site.register(App, AppAdmin)
admin.site.register(S3Bucket, S3Admin)
admin.site.register(User, UserAdmin)
admin.site.register(IPAllowlist, IPAllowlistAdmin)
admin.site.register(Feedback, FeedbackAdmin)
admin.site.register(ToolDeployment, ToolDeploymentAdmin)
