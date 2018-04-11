"""
Custom filters

See: http://www.django-rest-framework.org/api-guide/filtering/#custom-generic-filtering
"""

from django_filters.rest_framework import DjangoFilterBackend

from control_panel_api.models import S3Bucket
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

        return queryset.accessible_by(request.user)


class UserS3BucketFilter(DjangoFilterBackend):
    """
    Filter to get visible UserS3Bucket records.

    - Superusers see everything
    - Normal users see only records for buckets they have access.
      Normal users can also see records for other users that have access
      to same data (but permissions will enforce they can't change these
      records unless they're admin)
    """

    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)

        if is_superuser(request.user):
            return queryset

        accessible_buckets = S3Bucket.objects.accessible_by(request.user)

        return queryset.filter(s3bucket__in=accessible_buckets)
