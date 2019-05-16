from functools import wraps
import logging
import os
from urllib.parse import urljoin

from django.core import exceptions
from django.views.decorators.csrf import csrf_exempt
from djproxy.views import HttpProxy
from kubernetes import client, config

# This patch fixes incorrect base64 padding in the Kubernetes Python client.
# Hopefully it will be fixed in the next release.
from controlpanel.kubeapi import oidc_patch
from controlpanel.kubeapi.permissions import K8sPermissions


log = logging.getLogger(__name__)


def requires_kube_config(fn):

    @wraps(fn)
    def with_kube_config(*args, **kwargs):
        if 'KUBERNETES_SERVICE_HOST' in os.environ:
            config.load_incluster_config()

        else:
            config.load_kube_config()

        return fn(*args, **kwargs)

    return with_kube_config


class KubeAPIAuthMiddleware(object):
    """
    Add user's token to the Authorization header
    """

    @requires_kube_config
    def process_request(self, proxy, request, **kwargs):
        _, token = request.META.get("HTTP_AUTHORIZATION", " ").split(" ", 1)

        if token:
            auth = f"Bearer {token}"

        else:
            auth = client.Configuration().api_key["authorization"]

        kwargs["headers"]["Authorization"] = auth
        return kwargs


class KubeAPIProxy(HttpProxy):
    """
    Proxy requests to the Kubernetes cluster API
    """

    @property
    @requires_kube_config
    def base_url(self):
        return client.Configuration().host

    # Without this, we get SSL: CERTIFICATE_VERIFY_FAILED
    @property
    @requires_kube_config
    def verify_ssl(self):
        return client.Configuration().ssl_ca_cert

    @property
    def proxy_url(self):
        url = urljoin(self.base_url, self.kwargs.get('url', ''))
        return url

    permission_classes = [K8sPermissions]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxy_middleware.append(
            "controlpanel.kubeapi.views.KubeAPIAuthMiddleware",
        )

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        request = strip_path_prefix(request)
        self.check_permissions(request)
        return super().dispatch(request, *args, **kwargs)

    def check_permissions(self, request):
        for permission in self.get_permissions():
            if not permission.has_permission(request, self):
                raise exceptions.PermissionDenied()

    def get_permissions(self):
        return [permission() for permission in self.permission_classes]


def strip_path_prefix(request):
    if request.path_info.startswith("/api/k8s/"):
        request.path_info = request.path_info[9:]

    if request.path_info.startswith("/k8s/"):
        request.path_info = request.path_info[5:]

    return request
