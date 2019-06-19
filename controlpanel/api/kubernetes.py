import inspect

from crequest.middleware import CrequestMiddleware
from django.conf import settings

from controlpanel.kubeapi.views import kubernetes, load_kube_config


def config_from_current_user_id_token():
    request = CrequestMiddleware.get_request()
    config = kubernetes.client.Configuration()

    if request.user.is_authenticated and settings.ENABLED['k8s_rbac']:
        config.api_key_prefix['authorization'] = 'Bearer'
        config.api_key['authorization'] = request.session.get('oidc_id_token')

    return config


class RequestUserKubernetesClient:
    """
    Wraps kubernetes.client default configuration with currently logged-in
    user's credentials
    """

    def __init__(self):
        load_kube_config()
        config = config_from_current_user_id_token()
        self.api_client = kubernetes.client.ApiClient(config)

    def __getattr__(self, name):
        api_class = kubernetes.client.apis.__dict__.get(name)
        if api_class and inspect.isclass(api_class):
            return api_class(self.api_client)

        return super().__getattr__(name)
