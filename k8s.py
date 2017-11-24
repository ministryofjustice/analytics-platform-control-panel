import json
import os

from django.http import HttpResponse
import requests


class K8sProxy():

    def __init__(self, request, k8s_endpoint):
        self.request = request
        self.k8s_endpoint = k8s_endpoint
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
            auth=(self.config['k8s_username'], self.config['k8s_password']),
        )

    @property
    def _request_method(self):
        return self.request.method.lower()

    @property
    def _request_url(self):
        return f"{self.config['k8s_cluster_url']}/{self.k8s_endpoint}?{self._request_querystring}"

    @property
    def _request_querystring(self):
        return self.request.GET.urlencode()

    def _load_config(self):
        self.config = {
            'k8s_cluster_url': os.environ['K8S_CLUSTER_URL'],
            'k8s_username': os.environ['K8S_USERNAME'],
            'k8s_password': os.environ['K8S_PASSWORD'],
        }


def handler(request, k8s_endpoint):
    return K8sProxy(request, k8s_endpoint).handle()
