from django.http import HttpResponse
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
import requests


def proxy(request):
    return Request(request).dispatch()


class Request(object):

    def __init__(self, request):
        self.request = request
        self._config = Config()

    def dispatch(self):
        method = self.request.method.lower()
        host = self._config.host
        path = self.request.path[4:]  # path without '/k8s' prefix
        querystring = self.request.GET.urlencode()

        k8s_response = requests.request(
            method,
            f"{host}{path}?{querystring}",
            data=self.request.body,
            headers={'authorization': self._config.authorization},
            verify=self._config.ssl_ca_cert,
        )

        return HttpResponse(
            k8s_response.text,
            status=k8s_response.status_code,
            content_type='application/json'
        )


class Config(object):

    def __init__(self):
        try:
            config.load_incluster_config()
        except ConfigException as e:
            config.load_kube_config()

        self.host = client.configuration.host
        self.authorization = client.configuration.api_key['authorization']
        self.ssl_ca_cert = client.configuration.ssl_ca_cert
