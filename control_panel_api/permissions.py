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


class AppPermissions(IsSuperuser):
    pass


class UserPermissions(IsSuperuser):
    pass
