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

    def has_object_permission(self, request, view, obj):
        return is_superuser(request.user)


class AppPermissions(IsSuperuser):
    pass


class S3BucketPermissions(IsSuperuser):
    pass


class IsSelf(BasePermission):

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True

        if hasattr(request.user, 'auth0_id'):
            return view.kwargs.get('pk') == request.user.auth0_id

        return False

    def has_object_permission(self, request, view, obj):
        if super().has_object_permission(request, view, obj):
            return True

        return obj == request.user


class UserPermissions(IsSelf, IsSuperuser):
    pass
