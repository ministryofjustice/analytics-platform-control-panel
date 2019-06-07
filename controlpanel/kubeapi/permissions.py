from rest_framework.permissions import BasePermission


class K8sPermissions(BasePermission):
    """
    User can operate only in his namespace (unless superuser)
    """

    ALLOWED_APIS = [
        'api/v1',
        'apis/apps/v1beta2',
        'apis/extensions/v1beta1',
    ]

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        if not has_access_token(request) and not request.user.is_authenticated:
            return False

        path = request.path_info.lower()
        for api in self.ALLOWED_APIS:
            if path.startswith(f"{api}/namespaces/{request.user.k8s_namespace}/"):
                return True

        return False


def has_access_token(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION")
    return auth_header and (
        auth_header.startswith("Bearer ") or
        auth_header.startswith("JWT ")
    )
