from unittest.mock import patch

from django.conf import settings
import pytest

from controlpanel.api.models import User
from controlpanel.api.tools import (
    JupyterLab,
    RStudio,
    Tool,
    UnsupportedToolException,
)


@pytest.yield_fixture
def helm():
    with patch('controlpanel.api.tools.Helm') as Helm:
        yield Helm.return_value


@pytest.yield_fixture
def token_hex():
    with patch('controlpanel.api.tools.secrets') as secrets:
        yield secrets.token_hex


def test_when_unsupported_tool_raises_error():
    with pytest.raises(UnsupportedToolException):
        Tool.create('unsupported_tool')


def test_deploy_for_generic(helm, token_hex):
    user = User(username='AlIcE')
    username = user.username.lower()

    cookie_secret_proxy = 'cookie secret proxy'
    cookie_secret_tool = 'cookie secret tool'
    token_hex.side_effect = [
        cookie_secret_proxy,
        cookie_secret_tool
    ]

    class TestTool(Tool):
        name = "testtool"

    tool = TestTool()
    tool.deploy_for(user)

    conf = settings.TOOLS[tool.name]

    helm.upgrade_release.assert_called_with(
        f'{username}-{tool.name}',
        f'mojanalytics/{tool.name}',
        f'--namespace={user.k8s_namespace}',
        '--set', ','.join([
            f'username={username}',
            f'aws.iamRole={user.iam_role_name}',
            f'toolsDomain={settings.TOOLS_DOMAIN}',
            f'authProxy.cookieSecret={cookie_secret_proxy}',
            f'{tool.name}.secureCookieKey={cookie_secret_tool}',
            f'authProxy.auth0.domain={conf["domain"]}',
            f'authProxy.auth0.clientId={conf["client_id"]}',
            f'authProxy.auth0.clientSecret={conf["client_secret"]}',
        ])
    )
