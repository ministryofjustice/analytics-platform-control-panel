import logging

from rest_framework.permissions import BasePermission


ALLOWED_APIS = [
    'api/v1',
    'apis/apps/v1',
    'apis/apps/v1beta2',
    'apis/extensions/v1beta1',
]


log = logging.getLogger(__name__)


class K8sPermissions(BasePermission):
    """
    User can operate only in his namespace (unless superuser)
    """

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        path = request.path_info.lower()
        allowed_api = next(filter(path.startswith, ALLOWED_APIS), None)
        if not allowed_api:
            log.debug(f"{path} not in ALLOWED_APIS")
            return False

        if request.user.is_authenticated:
            ns = request.user.k8s_namespace
            if not path.startswith(f"{allowed_api}/namespaces/{ns}/"):
                log.debug(f"{path} not in user's namespace {ns}")
                return False
        else:
            if not has_access_token(request):
                log.debug(f"User not authenticated and bearer token missing")
                return False

        return True


def has_access_token(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION")
    return auth_header and (
        auth_header.startswith("Bearer ") or
        auth_header.startswith("JWT ")
    )
