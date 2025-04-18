"""
Custom filters

See: http://www.django-rest-framework.org/api-guide/filtering/#custom-generic-filtering
"""

# Third-party
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend

# First-party/Local
from controlpanel.api.models import S3Bucket
from controlpanel.api.permissions import is_superuser
from controlpanel.utils import get_domain_from_email


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


class AppS3BucketFilter(DjangoFilterBackend):
    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)

        if is_superuser(request.user):
            return queryset

        is_app_admin = Q(
            app__userapps__user=request.user,
            app__userapps__is_admin=True,
        )

        is_bucket_admin = Q(
            s3bucket__users3buckets__user=request.user,
            s3bucket__users3buckets__is_admin=True,
        )

        return queryset.filter(is_app_admin | is_bucket_admin).distinct()


class DashboardFilter(DjangoFilterBackend):
    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)

        if is_superuser(request.user):
            return queryset

        viewer_email = request.query_params.get("email")
        domain = get_domain_from_email(viewer_email)

        return queryset.filter(
            Q(viewers__email=viewer_email) | Q(whitelist_domains__name=domain)
        ).distinct()


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


class ParameterFilter(DjangoFilterBackend):
    """
    Filter to get visible Parameters.

    - Superusers see everything
    - Normal users see only Parameters they created
    """

    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)

        if is_superuser(request.user):
            return queryset

        return queryset.filter(created_by=request.user)
