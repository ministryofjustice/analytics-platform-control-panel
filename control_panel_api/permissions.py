"""
Custom permissions

See: http://www.django-rest-framework.org/api-guide/permissions/#custom-permissions
"""

from rest_framework.permissions import BasePermission


def is_superuser(user):
    return user and user.is_superuser


class AppPermissions(BasePermission):

    """
    Allows access only to super users.
    """

    def has_permission(self, request, view):
        return is_superuser(request.user)


class UserPermissions(BasePermission):
    """
    Allows access only to super users.
    """

    def has_permission(self, request, view):
        return is_superuser(request.user)
