from copy import deepcopy
import inspect
import kubernetes
import os

from crequest.middleware import CrequestMiddleware
from django.conf import settings

# This patch fixes incorrect base64 padding in the Kubernetes Python client.
# Hopefully it will be fixed in the next release.
from controlpanel.kubeapi import oidc_patch



def get_config():
    """
    Load Kubernetes config. Avoid running at import time.
    """

    if 'KUBERNETES_SERVICE_HOST' in os.environ:
        kubernetes.config.load_incluster_config()
    else:
        kubernetes.config.load_kube_config()

    config = kubernetes.client.Configuration()

    # The deepcopy is to avoid a race conditions on the credentials keys
    #
    # See: https://github.com/kubernetes-client/python/issues/932
    config.api_key_prefix = deepcopy(config.api_key_prefix)
    config.api_key = deepcopy(config.api_key)

    return config


class KubernetesClient:
    """
    Wraps kubernetes.client default configuration with currently logged-in
    user's credentials unless `use_cpanel_creds=True`, in that case the
    in-cluster (or ~/.kube/config) credentials are used.

    **IMPORTANT**: Do not pass `use_cpanel_creds=True` unless strictly
    necessary. The CP `ServiceAccount` has more privileges than normal users.
    For most operations performed by a user use their ID token to make requests
    to the k8s API.
    """

    def __init__(self, id_token=None, use_cpanel_creds=False):
        # if not use_cpanel_creds and not id_token:
        #     raise ValueError(
        #         "please provide an id_token (preferred) or pass use_cpanel_creds"
        #         "=True (this would cause the use of the host credentials so "
        #         "be careful when using it)"
        #     )

        if id_token and use_cpanel_creds:
            raise ValueError(
                "id_token and use_cpanel_creds can't be used together. "
                "Remember: avoid using the Control Panel credentials to talk with "
                "the k8s API unless stricly necessary."
            )

        config = get_config()

        if settings.ENABLED["k8s_rbac"] and not use_cpanel_creds:
            if id_token is None:
                request = CrequestMiddleware.get_request()
                if request and request.user and request.user.is_authenticated:
                    id_token = request.session.get('oidc_id_token')

            config.api_key_prefix['authorization'] = 'Bearer'
            config.api_key['authorization'] = id_token

        self.api_client = kubernetes.client.ApiClient(config)

    def __getattr__(self, name):
        api_class = kubernetes.client.apis.__dict__.get(name)
        if api_class and inspect.isclass(api_class):
            return api_class(self.api_client)

        return super().__getattr__(name)
