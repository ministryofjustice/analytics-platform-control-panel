import os
import secrets

from django.conf import settings
from rest_framework.exceptions import APIException

from control_panel_api.helm import Helm


SUPPORTED_TOOL_NAMES = [
    'rstudio',
]


class UnsupportedToolException(APIException):
    tools_list = ", ".join(SUPPORTED_TOOL_NAMES)

    status_code = 400
    default_detail = f'Unsupported tool, tool_name must be one of: {tools_list}'
    default_code = 'unsupported_tool'


class Tool():

    def __init__(self, name):
        self.name = self._validate_name(name)
        self.helm = Helm()

        self.auth_client_domain = self._get_auth_client_config('domain')
        self.auth_client_id = self._get_auth_client_config('id')
        self.auth_client_secret = self._get_auth_client_config('secret')

    def deploy_for(self, user):
        """
        Deploy the given tool in the user namespace.

        >>> rstudio = Tool('rstudio')
        >>> rstudio.deploy_for(alice)
        """

        username = user.username.lower()
        auth_proxy_cookie_secret = secrets.token_hex(32)
        tool_cookie_secret = secrets.token_hex(32)

        self.helm.upgrade_release(
            f'{username}-{self.name}',
            f'mojanalytics/{self.name}',
            '--namespace', user.k8s_namespace,
            '--set', f'Username={username}',
            '--set', f'aws.iamRole={user.iam_role_name}',
            '--set', f'toolsDomain={settings.TOOLS_DOMAIN}',
            '--set', f'authProxy.cookieSecret={auth_proxy_cookie_secret}',
            '--set', f'{self.name}.secureCookieKey={tool_cookie_secret}',
            '--set', f'authProxy.auth0.domain={self.auth_client_domain}',
            '--set', f'authProxy.auth0.clientId={self.auth_client_id}',
            '--set', f'authProxy.auth0.clientSecret={self.auth_client_secret}',
        )

    def _get_auth_client_config(self, key):
        setting_key = f'{self.name}_AUTH_CLIENT_{key}'
        return getattr(settings, setting_key.upper())

    def _validate_name(self, name):
        if not name in SUPPORTED_TOOL_NAMES:
            raise UnsupportedToolException

        return name
