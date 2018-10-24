from unittest.case import TestCase
from unittest.mock import patch

from django.test import override_settings

from control_panel_api.models import User
from control_panel_api.tools import RStudio, UnsupportedToolException, Tools, BaseTool, ToolsRepository, JupyterLab


class ToolsTestCase(TestCase):

    TOOLS_DOMAIN = 'example.com'
    TOOL_AUTH_CLIENT_DOMAIN = 'auth.example.com'
    TOOL_AUTH_CLIENT_ID = '42'
    TOOL_AUTH_CLIENT_SECRET = 'secret'

    def test_when_unsupported_tool_raises_error(self):
        with self.assertRaises(UnsupportedToolException):
            Tools['unsupported_tool']()

    @override_settings(
        TOOLS_DOMAIN=TOOLS_DOMAIN,
        RANDOTOOL_AUTH_CLIENT_DOMAIN=TOOL_AUTH_CLIENT_DOMAIN,
        RANDOTOOL_AUTH_CLIENT_ID=TOOL_AUTH_CLIENT_ID,
        RANDOTOOL_AUTH_CLIENT_SECRET=TOOL_AUTH_CLIENT_SECRET,
    )
    @patch('secrets.token_hex')
    @patch('control_panel_api.tools.Helm.upgrade_release')
    def test_deploy_for_generic(self, mock_helm_upgrade_release, mock_token_hex):
        tool_name = 'randotool'
        user = User(username='AlIcE')
        username = user.username.lower()

        cookie_secret_proxy = 'cookie secret proxy'
        cookie_secret_tool = 'cookie secret tool'
        mock_token_hex.side_effect = [
            cookie_secret_proxy,
            cookie_secret_tool
        ]

        class RandoTool(BaseTool):
            name = 'randotool'

        tool = RandoTool()
        tool.deploy_for(user)

        mock_helm_upgrade_release.assert_called_with(
            f'{username}-{tool_name}',
            f'mojanalytics/{tool_name}',
            '--namespace', user.k8s_namespace,
            '--set', f'username={username}',
            '--set', f'aws.iamRole={user.iam_role_name}',
            '--set', f'toolsDomain={self.TOOLS_DOMAIN}',
            '--set', f'authProxy.cookieSecret={cookie_secret_proxy}',
            '--set', f'{tool_name}.secureCookieKey={cookie_secret_tool}',
            '--set', f'authProxy.auth0.domain={self.TOOL_AUTH_CLIENT_DOMAIN}',
            '--set', f'authProxy.auth0.clientId={self.TOOL_AUTH_CLIENT_ID}',
            '--set', f'authProxy.auth0.clientSecret={self.TOOL_AUTH_CLIENT_SECRET}',
        )


class TestToolsRepository(TestCase):

    def test_repository_init(self):
        tr = ToolsRepository(RStudio, JupyterLab)
        self.assertDictEqual(tr.data, {
            'rstudio': RStudio,
            'jupyter-lab': JupyterLab
        })

    def test_getattr_exception(self):
        tr = ToolsRepository()
        with self.assertRaises(UnsupportedToolException):
            tr['foo']()
