import logging
import os

from django.conf import settings
from djproxy.views import HttpProxy
from kubernetes import client, config

# This patch fixes incorrect base64 padding in the Kubernetes Python client.
# Hopefully it will be fixed in the next release.
from controlpanel.kubeapi import oidc_patch


log = logging.getLogger(__name__)


if 'KUBERNETES_SERVICE_HOST' in os.environ:
    config.load_incluster_config()

else:
    config.load_kube_config()



class KubeAPIAuthMiddleware(object):
    """
    Add user's token to the Authorization header
    """

    def process_request(self, proxy, request, **kwargs):
        if settings.ENABLED["k8s_rbac"]:
            _, token = request.META["HTTP_AUTHORIZATION"].split(" ", 1)
            auth = f"Bearer {token}"

        else:
            auth = client.Configuration().api_key["authorization"]

        log.debug("auth = %s", auth)

        kwargs["headers"]["Authorization"] = auth
        return kwargs


class KubeAPIProxy(HttpProxy):
    """
    Proxy requests to the Kubernetes cluster API
    """

    base_url = client.Configuration().host

    # Without this, we get SSL: CERTIFICATE_VERIFY_FAILED
    verify_ssl = client.Configuration().ssl_ca_cert

    proxy_middleware = ["controlpanel.kubeapi.views.KubeAPIAuthMiddleware"]
