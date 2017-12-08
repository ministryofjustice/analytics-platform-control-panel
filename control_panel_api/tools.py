import os

from django.conf import settings

from control_panel_api.helm import Helm


class Tool():

    def __init__(self, name):
        self.name = name
        self.helm = Helm()
        self.load_auth_client_config()

    def deploy_for(self, user):
        """
        Deploy the given tool in the user namespace.

        >>> rstudio = Tool('rstudio')
        >>> rstudio.deploy_for(alice)
        """
        self.helm.upgrade_release(
            f'{username}-{self.name}',
            f'mojanalytics/{self.name}',
            '--namespace', user.k8s_namespace,
            '--set', f'Username={user.username.lower()}',
            '--set', f'aws.iamRole={user.iam_role_name}',
            '--set', 'authProxy.auth.domain=' + self.auth_client["domain"],
            '--set', 'authProxy.auth.clientId=' + self.auth_client["id"],
            '--set', 'authProxy.auth.clientSecret=' + self.auth_client["secret"],
        )

    def load_auth_client_config(self):
        """
        Read Auth client config into `self.auth_client`

        This dictionary has 3 keys:
          - `domain` with value `settings.OIDC_DOMAIN`
          - `id` with value from `${TOOL}_AUTH_CLIENT_ID`
          - `secret` with value from `${TOOL}_AUTH_CLIENT_SECRET`

        e.g. if the tool name is `rstudio`:
          - `domain` will be read from `settings.OIDC_DOMAIN`
          - `id` will be read from `RSTUDIO_AUTH_CLIENT_ID`
          - `secret` will be read from `RSTUDIO_AUTH_CLIENT_SECRET`
        """
        tool_auth_prefix = f'{self.name.upper()}_AUTH_CLIENT'

        self.auth_client = {
            'domain': settings.OIDC_DOMAIN,
            'id': os.environ[f'{tool_auth_prefix}_ID'],
            'secret': os.environ[f'{tool_auth_prefix}_SECRET'],
        }
