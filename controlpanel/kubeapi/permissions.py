from rest_framework.permissions import BasePermission


class K8sPermissions(BasePermission):
    """
    User can operate only in his namespace (unless superuser)
    """

    ALLOWED_APIS = [
        'api/v1',
        'apis/apps/v1beta2',
    ]

    def has_permission(self, request, view):
        if not request.user or request.user.is_anonymous:
            return False

        if request.user and request.user.is_superuser:
            return True

        path = request.path.lower()
        for api in self.ALLOWED_APIS:
            if path.startswith(
                    f'/api/k8s/{api}/namespaces/{request.user.k8s_namespace}/'):
                return True

        return False
