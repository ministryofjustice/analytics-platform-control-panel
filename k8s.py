import json
import os

from django.http import HttpResponse
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
import requests


class K8sProxy():

    def __init__(self, request):
        self.request = request
        self._load_config()

    def handle(self):
        k8s_response = self._make_k8s_request()

        return HttpResponse(
            k8s_response.text,
            status=k8s_response.status_code,
            content_type='application/json'
        )

    def _make_k8s_request(self):
        headers = {
            'accept': 'application/json',
            'authorization': self.cluster_authorization,
        }
        requests_func = getattr(requests, self._request_method)
        return requests_func(
            self._request_url,
            headers=headers,
            verify=False,
        )

    @property
    def _request_method(self):
        return self.request.method.lower()

    @property
    def _request_url(self):
        return f"{self.cluster_url}{self._request_path}?{self._request_querystring}"

    @property
    def _request_path(self):
        return self.request.path[4:]  # path without '/k8s' prefix

    @property
    def _request_querystring(self):
        return self.request.GET.urlencode()

    def _load_config(self):
        try:
            config.load_incluster_config()
        except ConfigException as e:
            config.load_kube_config()

        self.cluster_url = client.configuration.host
        self.cluster_authorization = client.configuration.api_key[
            'authorization']


def handler(request):
    return K8sProxy(request).handle()
