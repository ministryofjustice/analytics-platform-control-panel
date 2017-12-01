from django.http import HttpResponse
from kubernetes import (
    client as k8s_client,
    config as k8s_config,
)
from kubernetes.config.config_exception import ConfigException
import requests


def proxy(request):
    return Request(request).dispatch()


class Request(object):

    def __init__(self, request):
        self.request = request
        self._load_config()

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

    def _load_config(self):
        config.load()
        self._config = config


class Config(object):

    def __init__(self):
        self._loaded = False

    def load(self):
        """
        Load the k8s configuration.

        The configuration is only loaded the first time.
        """
        if not self._loaded:
            try:
                k8s_config.load_incluster_config()
            except ConfigException as e:
                k8s_config.load_kube_config()

            self.host = k8s_client.configuration.host
            self.authorization = k8s_client.configuration.api_key[
                'authorization']
            self.ssl_ca_cert = k8s_client.configuration.ssl_ca_cert

            self._loaded = True


config = Config()
