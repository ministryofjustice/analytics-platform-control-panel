# Standard library
from urllib.parse import urljoin

# Third-party
from django.core import exceptions
from django.views.decorators.csrf import csrf_exempt
from djproxy.views import HttpProxy

# First-party/Local
from controlpanel import api
from controlpanel.jwt import JWT
from controlpanel.kubeapi.permissions import K8sPermissions


class KubeAPIAuthMiddleware(object):
    """
    Add user's token to the Authorization header
    """

    def process_request(self, proxy, request, **kwargs):
        jwt = JWT.from_auth_header(request)
        kwargs["headers"]["Authorization"] = f"Bearer {str(jwt)}"
        return kwargs


class KubeAPIProxy(HttpProxy):
    """
    Proxy requests to the Kubernetes cluster API
    """

    @property
    def base_url(self):
        return self.kubernetes_config.host

    # Without this, we get SSL: CERTIFICATE_VERIFY_FAILED
    @property
    def verify_ssl(self):
        return self.kubernetes_config.ssl_ca_cert

    @property
    def proxy_url(self):
        return urljoin(self.base_url, self.kwargs.get("url", ""))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kubernetes_config = api.kubernetes.get_config()
        self.proxy_middleware.append(
            "controlpanel.kubeapi.views.KubeAPIAuthMiddleware",
        )

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        request = strip_path_prefix(request)
        request = fix_leading_space_headers(request)

        if not K8sPermissions().has_permission(request, self):
            raise exceptions.PermissionDenied()

        return super().dispatch(request, *args, **kwargs)


def strip_path_prefix(request):
    if request.path_info.startswith("/api/k8s/"):
        request.path_info = request.path_info[9:]

    # accept old kubernetes proxy URLs
    if request.path_info.startswith("/k8s/"):
        request.path_info = request.path_info[5:]

    return request


def fix_leading_space_headers(request):
    # requests 2.11 raises InvalidHeader if the value has leading spaces
    for key, value in request.META.items():
        if isinstance(value, str):
            request.META[key] = value.lstrip(" ")

    return request
