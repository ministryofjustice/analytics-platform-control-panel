import json
import os

from django.http import HttpResponse
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
        import pdb
        pdb.set_trace()

        requests_func = getattr(requests, self._request_method)
        return requests_func(
            self._request_url,
            headers={'accept': 'application/json'},
            verify=False,
            auth=(self.cluster_username, self.cluster_password),
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
        self.cluster_url = os.environ['K8S_CLUSTER_URL']
        self.cluster_username = os.environ['K8S_USERNAME']
        self.cluster_password = os.environ['K8S_PASSWORD']


def handler(request):
    return K8sProxy(request).handle()
