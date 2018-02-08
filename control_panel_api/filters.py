"""
Custom filters

See: http://www.django-rest-framework.org/api-guide/filtering/#custom-generic-filtering
"""

from django_filters.rest_framework import DjangoFilterBackend

from control_panel_api.permissions import is_superuser


class SuperusersOnlyFilter(DjangoFilterBackend):
    """
    Superusers can see everything. Other users can't see anything
    """

    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)

        if is_superuser(request.user):
            return queryset

        return queryset.none()


class AppFilter(SuperusersOnlyFilter):
    """
    Filter to get visible apps.

    Currently superusers see everything, others see nothing.
    """

    pass


class S3BucketFilter(DjangoFilterBackend):
    """
    Filter to get visible S3 buckets.

    - Superusers see everything
    - Normal users see only S3 buckets they have access to (looking at
      UserS3Bucket records)
    """

    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)

        if is_superuser(request.user):
            return queryset

        return queryset.filter(users3buckets__user=request.user)


class UserFilter(DjangoFilterBackend):
    """
    Filter to get visible users.

    Currently superusers see everything, normal users see only themselves,
    unauthenticated users see nothing.
    """

    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)

        if is_superuser(request.user):
            return queryset

        return queryset.filter(pk=request.user.pk)
