"""
Custom filters

See: http://www.django-rest-framework.org/api-guide/filtering/#custom-generic-filtering
"""
from rest_framework.filters import BaseFilterBackend

from control_panel_api.permissions import is_superuser


class SuperusersOnlyFilter(BaseFilterBackend):
    """
    Superusers can see everything. Other users can't see anything
    """

    def filter_queryset(self, request, queryset, view):
        if is_superuser(request.user):
            return queryset
        else:
            return queryset.none()


class AppFilter(SuperusersOnlyFilter):
    """
    Filter to get visible apps.

    Currently superusers see everything, others see nothing.
    """

    pass


class S3BucketFilter(SuperusersOnlyFilter):
    """
    Filter to get visible users.

    Currently superusers see everything, others see nothing.
    """

    pass


class UserFilter(SuperusersOnlyFilter):
    """
    Filter to get visible users.

    Currently superusers see everything, others see nothing.
    """

    pass
