import json
import os

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


class Proxy(object):

    def __init__(self, request):
        self.request = request
        self._config = Config()

    def handle(self):
        k8s_response = self._make_k8s_request()

        return HttpResponse(
            k8s_response.text,
            status=k8s_response.status_code,
            content_type='application/json'
        )

    def _make_k8s_request(self):
        headers = {
            'authorization': self._config.authorization,
        }
        requests_func = getattr(requests, self._request_method)
        return requests_func(
            self._request_url,
            data=self.request.body,
            headers=headers,
            verify=self._config.ssl_ca_cert,
        )

    @property
    def _request_method(self):
        return self.request.method.lower()

    @property
    def _request_url(self):
        return f"{self._config.host}{self._request_path}?{self._request_querystring}"

    @property
    def _request_path(self):
        return self.request.path[4:]  # path without '/k8s' prefix

    @property
    def _request_querystring(self):
        return self.request.GET.urlencode()

    def _load_config(self):
        pass



def handler(request):
    return Proxy(request).handle()
