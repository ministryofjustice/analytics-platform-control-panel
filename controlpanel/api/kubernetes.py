import inspect

from crequest.middleware import CrequestMiddleware
from django.conf import settings

from controlpanel.kubeapi.views import kubernetes, load_kube_config


class KubernetesClient:
    """
    Wraps kubernetes.client default configuration with currently logged-in
    user's credentials
    """

    def __init__(self, id_token=None):
        load_kube_config()
        config = kubernetes.client.Configuration()

        if settings.ENABLED['k8s_rbac']:

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
