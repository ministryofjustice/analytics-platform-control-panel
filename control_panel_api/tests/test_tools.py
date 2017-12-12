from unittest.case import TestCase

from django.test import override_settings
from unittest.mock import patch

from control_panel_api.models import User
from control_panel_api.tools import Tool, UnsupportedToolException


class ToolsTestCase(TestCase):

    TOOLS_DOMAIN = 'example.com'
    TOOL_AUTH_CLIENT_DOMAIN = 'auth.example.com'
    TOOL_AUTH_CLIENT_ID = '42'
    TOOL_AUTH_CLIENT_SECRET = 'secret'

    def test_when_unsupported_tool_raises_error(self):
        with self.assertRaises(UnsupportedToolException):
            Tool('unsupported_tool')

    @override_settings(
        TOOLS_DOMAIN=TOOLS_DOMAIN,
        RSTUDIO_AUTH_CLIENT_DOMAIN=TOOL_AUTH_CLIENT_DOMAIN,
        RSTUDIO_AUTH_CLIENT_ID=TOOL_AUTH_CLIENT_ID,
        RSTUDIO_AUTH_CLIENT_SECRET=TOOL_AUTH_CLIENT_SECRET,
    )
    @patch('secrets.token_hex')
    @patch('control_panel_api.tools.Helm.upgrade_release')
    def test_deploy_for(self, mock_helm_upgrade_release, mock_token_hex):
        tool_name = 'rstudio'
        user = User(username='AlIcE')
        username = user.username.lower()

        cookie_secret_proxy = 'cookie secret proxy'
        cookie_secret_tool = 'cookie secret tool'
        mock_token_hex.side_effect = [
            cookie_secret_proxy,
            cookie_secret_tool
        ]

        tool = Tool(tool_name)
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
