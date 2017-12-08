import os
import secrets

from django.conf import settings

from control_panel_api.helm import Helm


class Tool():

    def __init__(self, name):
        self.name = name
        self.helm = Helm()

        self.auth_client_domain = _get_auth_client_config('domain')
        self.auth_client_id = _get_auth_client_config('id')
        self.auth_client_secret = _get_auth_client_config('secret')

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
            chart=f'mojanalytics/{self.name}',
            release=f'{username}-{self.name}',
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
