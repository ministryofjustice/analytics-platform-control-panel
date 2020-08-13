"""
Custom permissions

See: http://www.django-rest-framework.org/api-guide/permissions/#custom-permissions
"""

from rest_framework.permissions import BasePermission

from controlpanel.api.models import S3Bucket
from controlpanel.api.rules import is_bucket_admin
from controlpanel.api.serializers import UserS3BucketSerializer


def is_superuser(user):
    return user and user.is_superuser


class IsSuperuser(BasePermission):
    """
    Only superusers are authorised
    """

    def has_permission(self, request, view):
        return is_superuser(request.user)


class RulesBasePermissions(BasePermission):
    """
    Delegate to permissions defined in `controlpanel.api.rules`
    """

    resource = None

    def has_permission(self, request, view):
        return request.user.has_perm(f'api.{view.action}_{self.resource}')

    def has_object_permission(self, request, view, obj):
        return request.user.has_perm(f'api.{view.action}_{self.resource}', obj)


class AppPermissions(RulesBasePermissions):
    resource = 'app'


class S3BucketPermissions(RulesBasePermissions):
    resource = 's3bucket'


class UserPermissions(RulesBasePermissions):
    resource = 'user'


class AppS3BucketPermissions(RulesBasePermissions):
    resource = 'apps3bucket'


class UserS3BucketPermissions(RulesBasePermissions):
    resource = 'users3bucket'

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        ok = super().has_permission(request, view)

        if not ok:
            return False

        if view.action == 'create':

            serializer = UserS3BucketSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            return is_bucket_admin(request.user, serializer.validated_data['s3bucket'])

        return ok


class ToolPermissions(RulesBasePermissions):
    resource = 'tool'


class ParameterPermissions(RulesBasePermissions):
    resource = 'parameter'
