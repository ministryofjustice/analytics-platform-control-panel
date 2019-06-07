from functools import wraps
import os
from urllib.parse import urljoin

from django.core import exceptions
from django.views.decorators.csrf import csrf_exempt
from djproxy.views import HttpProxy
import kubernetes

# This patch fixes incorrect base64 padding in the Kubernetes Python client.
# Hopefully it will be fixed in the next release.
from controlpanel.kubeapi import oidc_patch
from controlpanel.kubeapi.permissions import K8sPermissions


def load_kube_config():
    """
    Load Kubernetes config. Avoid running at import time.
    """

    if 'KUBERNETES_SERVICE_HOST' in os.environ:
        kubernetes.config.load_incluster_config()

    else:
        kubernetes.config.load_kube_config()


class KubeAPIAuthMiddleware(object):
    """
    Add user's token to the Authorization header
    """

    def process_request(self, proxy, request, **kwargs):
        _, token = request.META.get("HTTP_AUTHORIZATION", " ").split(" ", 1)

        if token:
            auth = f"Bearer {token}"

        else:
            auth = kubernetes.client.Configuration().api_key["authorization"]

        kwargs["headers"]["Authorization"] = auth
        return kwargs


class KubeAPIProxy(HttpProxy):
    """
    Proxy requests to the Kubernetes cluster API
    """

    @property
    def base_url(self):
        return kubernetes.client.Configuration().host

    # Without this, we get SSL: CERTIFICATE_VERIFY_FAILED
    @property
    def verify_ssl(self):
        return kubernetes.client.Configuration().ssl_ca_cert

    @property
    def proxy_url(self):
        return urljoin(self.base_url, self.kwargs.get('url', ''))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        load_kube_config()
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

    # accept old API URLs
    if request.path_info.startswith("/k8s/"):
        request.path_info = request.path_info[5:]

    return request


def fix_leading_space_headers(request):
    # requests 2.11 raises InvalidHeader if the value has leading spaces
    for key, value in request.META.items():
        if isinstance(value, str):
            request.META[key] = value.lstrip(" ")

    return request
