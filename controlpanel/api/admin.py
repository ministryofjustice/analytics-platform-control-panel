# Third-party
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

# First-party/Local
from controlpanel.api.models import App, Feedback, IPAllowlist, S3Bucket, User


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


admin.site.register(App, AppAdmin)
admin.site.register(S3Bucket, S3Admin)
admin.site.register(User, UserAdmin)
admin.site.register(IPAllowlist, IPAllowlistAdmin)
admin.site.register(Feedback, FeedbackAdmin)
