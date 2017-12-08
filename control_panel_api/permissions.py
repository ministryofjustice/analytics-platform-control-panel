"""
Custom permissions

See: http://www.django-rest-framework.org/api-guide/permissions/#custom-permissions
"""

from rest_framework.permissions import BasePermission


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
        if not request.user:
            return False

        if is_superuser(request.user):
            return True

        username = request.user.username.lower()
        if not username:
            return False

        path = request.path.lower()

        for api in self.ALLOWED_APIS:
            if path.startswith(f'/k8s/{api}/namespaces/user-{username}/'):
                return True

        return False


class AppPermissions(IsSuperuser):
    pass


class S3BucketPermissions(IsSuperuser):
    pass


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
