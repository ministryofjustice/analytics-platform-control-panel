"""
Custom permissions

See: http://www.django-rest-framework.org/api-guide/permissions/#custom-permissions
"""

from rest_framework.permissions import BasePermission

from control_panel_api.models import S3Bucket
from control_panel_api.serializers import UserS3BucketSerializer


def is_superuser(user):
    return user and user.is_superuser


class IsSuperuser(BasePermission):
    """
    Only superusers are authorised
    """

    def has_permission(self, request, view):
        return is_superuser(request.user)


class K8sPermissions(BasePermission):
    """
    User can operate only in his namespace (unless superuser)
    """

    ALLOWED_APIS = [
        'api/v1',
        'apis/apps/v1beta2',
    ]

    def has_permission(self, request, view):
        if not request.user or request.user.is_anonymous():
            return False

        if is_superuser(request.user):
            return True

        path = request.path.lower()
        for api in self.ALLOWED_APIS:
            if path.startswith(
                    f'/k8s/{api}/namespaces/{request.user.k8s_namespace}/'):
                return True

        return False


class AppPermissions(IsSuperuser):
    pass


class S3BucketPermissions(BasePermission):
    """
    - Superusers can do anything
    - Normal users can create S3 buckets and list/retrieve buckets they have
      access to

    NOTE: Filters are applied before permissions
    """

    def has_permission(self, request, view):
        if is_superuser(request.user):
            return True

        if request.user.is_anonymous():
            return False

        return view.action in ('create', 'list', 'retrieve')


class UserPermissions(BasePermission):
    """
    Superusers can do anything, normal users can only access themselves,
    unauthenticated users cannot do anything
    """

    def has_permission(self, request, view):
        if is_superuser(request.user):
            return True

        if request.user.is_anonymous():
            return False

        return view.action not in ('create', 'destroy', 'list')

    def has_object_permission(self, request, view, obj):
        if is_superuser(request.user):
            return True

        return request.user == obj


class UserS3BucketPermissions(BasePermission):
    def has_permission(self, request, view):
        if is_superuser(request.user):
            return True

        if request.user.is_anonymous():
            return False

        if view.action != 'create':
            return True

        serializer = UserS3BucketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        accessible_buckets = S3Bucket.objects.accessible_by_admin(request.user)

        if serializer.validated_data['s3bucket'] in accessible_buckets:
            return True

    def has_object_permission(self, request, view, obj):
        if is_superuser(request.user):
            return True

        if obj.user_is_admin(request.user):
            return True

        if obj.s3bucket in S3Bucket.objects.accessible_by_admin(request.user):
            return True


class ToolDeploymentPermissions(BasePermission):
    def has_permission(self, request, view):
        return not request.user.is_anonymous()
