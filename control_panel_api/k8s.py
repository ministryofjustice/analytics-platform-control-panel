from django.conf import settings
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

    def dispatch(self):
        method = self.request.method.lower()
        host = self.config.host
        path = self.request.path[4:]  # path without '/k8s' prefix
        querystring = self.request.GET.urlencode()

        k8s_response = requests.request(
            method,
            f"{host}{path}?{querystring}",
            data=self.request.body,
            headers={'authorization': self.authorization},
            verify=self.config.ssl_ca_cert,
        )

        return HttpResponse(
            k8s_response.text,
            status=k8s_response.status_code,
            content_type='application/json'
        )

    @property
    def authorization(self):
        if settings.ENABLED['k8s_rbac']:
            return self.request.META['HTTP_AUTHORIZATION'].replace('JWT', 'Bearer')

        return self.config.authorization

    @property
    def config(self):
        if not hasattr(self, '_config'):
            config.load()
            self._config = config

        return self._config


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
                from control_panel_api import k8s_patch
                k8s_config.load_kube_config()

            conf = k8s_client.configuration.Configuration()
            self.host = conf.host
            if not settings.ENABLED['k8s_rbac']:
                self.authorization = conf.api_key['authorization']
            self.ssl_ca_cert = conf.ssl_ca_cert

            self._loaded = True


config = Config()
