import secrets
from collections import UserDict

from django.conf import settings
from django.utils.functional import cached_property
from rest_framework.exceptions import APIException

from control_panel_api.helm import Helm
from control_panel_api.utils import sanitize_environment_variable


class HelmToolDeployMixin:

    @cached_property
    def helm(self):
        return Helm()


class Auth0ClientConfigMixin:

    def _get_auth_client_config(self, key):
        setting_key = sanitize_environment_variable(
            f'{self.name}_AUTH_CLIENT_{key}')
        return getattr(settings, setting_key.upper())

    @cached_property
    def auth_client_domain(self):
        return self._get_auth_client_config('domain')

    @cached_property
    def auth_client_id(self):
        return self._get_auth_client_config('id')

    @cached_property
    def auth_client_secret(self):
        return self._get_auth_client_config('secret')


SUPPORTED_TOOL_NAMES = [
    'rstudio',
    'jupyter-lab',
    'airflow-sqlite',
]


class UnsupportedToolException(APIException):
    tools_list = ", ".join(SUPPORTED_TOOL_NAMES)

    status_code = 400
    default_detail = f'Unsupported tool, tool_name must be one of: {tools_list}'
    default_code = 'unsupported_tool'


class BaseTool(HelmToolDeployMixin, Auth0ClientConfigMixin):
    name = None

    @property
    def chart_name(self):
        return f'mojanalytics/{self.name}'

    def release_name(self, username):
        return f'{username}-{self.name}'

    def deploy_params(self, user):
        auth_proxy_cookie_secret = secrets.token_hex(32)
        tool_cookie_secret = secrets.token_hex(32)
        username = user.username.lower()

        return [
            '--set', f'username={username}',
            '--set', f'aws.iamRole={user.iam_role_name}',
            '--set', f'toolsDomain={settings.TOOLS_DOMAIN}',
            '--set', f'authProxy.cookieSecret={auth_proxy_cookie_secret}',
            '--set', f'{self.name}.secureCookieKey={tool_cookie_secret}',
            '--set', f'authProxy.auth0.domain={self.auth_client_domain}',
            '--set', f'authProxy.auth0.clientId={self.auth_client_id}',
            '--set', f'authProxy.auth0.clientSecret={self.auth_client_secret}',
        ]

    def deploy_for(self, user):
        """
        Deploy the given tool in the user namespace.
        >>> class RStudio(BaseTool):
        ...     name = 'rstudio'
        >>> rstudio = RStudio()
        >>> rstudio.deploy_for(alice)
        """

        username = user.username.lower()
        deploy_params = self.deploy_params(user)
        self.helm.upgrade_release(
            self.release_name(username),
            self.chart_name,
            '--namespace', user.k8s_namespace,
            *deploy_params
        )


class RStudio(BaseTool):
    name = 'rstudio'


class JupyterLab(BaseTool):
    name = 'jupyter-lab'

    def release_name(self, username):
        return f'{self.name}-{username}'

    def deploy_params(self, user):
        auth_proxy_cookie_secret = secrets.token_hex(32)

        return [
            '--set', f'Username={user.username.lower()}',
            '--set', f'aws.iamRole={user.iam_role_name}',
            '--set', f'toolsDomain={settings.TOOLS_DOMAIN}',
            '--set', f'cookie_secret={auth_proxy_cookie_secret}',
            '--set', f'authProxy.auth0_domain={self.auth_client_domain}',
            '--set', f'authProxy.auth0_client_id={self.auth_client_id}',
            '--set', f'authProxy.auth0_client_secret={self.auth_client_secret}',
        ]


class Airflow(BaseTool):
    name = 'airflow-sqlite'

    def deploy_params(self, user):
        auth_proxy_cookie_secret = secrets.token_hex(32)

        return [
            '--set', f'Username={user.username.lower()}',
            '--set', f'aws.iamRole={user.iam_role_name}',
            '--set', f'toolsDomain={settings.TOOLS_DOMAIN}',
            '--set', f'cookie_secret={auth_proxy_cookie_secret}',
            '--set', f'authProxy.auth0_domain={self.auth_client_domain}',
            '--set', f'authProxy.auth0_client_id={self.auth_client_id}',
            '--set', f'authProxy.auth0_client_secret={self.auth_client_secret}',
            '--set', f'airflow.secretKey={settings.AIRFLOW_SECRET_KEY}',
            '--set', f'airflow.fernetKey={settings.AIRFLOW_FERNET_KEY}',
        ]


class ToolsRepository(UserDict):

    def __init__(self, *tools):
        super().__init__({toolcls.name: toolcls for toolcls in tools})

    def __getitem__(self, item):
        try:
            return super().__getitem__(item)
        except KeyError:
            raise UnsupportedToolException()


Tools = ToolsRepository(RStudio, JupyterLab, Airflow)
