from django.contrib import admin
from controlpanel.api.models.user import User


def make_migration_pending(modeladmin, request, queryset):
    queryset.update(migration_state=User.PENDING)


make_migration_pending.short_description = "Mark selected users as pending migration"


class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "auth0_id", "email", "is_superuser", "migration_state")
    actions = [make_migration_pending]
    exclude = ("password",)


admin.site.register(User, UserAdmin)
