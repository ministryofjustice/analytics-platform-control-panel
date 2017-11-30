from django.http import HttpResponse
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
import requests


class Config(object):

    def __init__(self):
        try:
            config.load_incluster_config()
        except ConfigException as e:
            config.load_kube_config()

        self.host = client.configuration.host
        self.authorization = client.configuration.api_key[
            'authorization']
        self.ssl_ca_cert = client.configuration.ssl_ca_cert


class Request(object):

    def __init__(self, request):
        self.request = request
        self._config = Config()

    def make(self):
        k8s_response = requests.request(
            self.method,
            self.url,
            data=self.request.body,
            headers={'authorization': self._config.authorization},
            verify=self._config.ssl_ca_cert,
        )

        return HttpResponse(
            k8s_response.text,
            status=k8s_response.status_code,
            content_type='application/json'
        )

    @property
    def method(self):
        return self.request.method.lower()

    @property
    def url(self):
        return f"{self._config.host}{self.path}?{self.querystring}"

    @property
    def path(self):
        return self.request.path[4:]  # path without '/k8s' prefix

    @property
    def querystring(self):
        return self.request.GET.urlencode()


def proxy(request):
    return Request(request).make()
