from unittest.mock import patch

from django.conf import settings
from model_mommy import mommy
import pytest

from controlpanel.api.models import Tool, ToolDeployment, User


@pytest.fixture
def tool(db):
    return mommy.make('api.Tool')


@pytest.yield_fixture
def token_hex():
    with patch('controlpanel.api.models.tool.secrets') as secrets:
        yield secrets.token_hex


def test_deploy_for_generic(helm, token_hex, tool, users):
    cookie_secret_proxy = 'cookie secret proxy'
    cookie_secret_tool = 'cookie secret tool'
    token_hex.side_effect = [
        cookie_secret_proxy,
        cookie_secret_tool
    ]

    user = users['normal_user']
    tool_deployment = ToolDeployment(tool, user)
    tool_deployment.save()

    helm.upgrade_release.assert_called_with(
        f'{tool.chart_name}-{user.slug}',
        f'mojanalytics/{tool.chart_name}',
        # '--version', tool.version,
        '--namespace', user.k8s_namespace,
        '--set', f'username={user.username}',
        '--set', f'Username={user.username}',
        '--set', f'aws.iamRole={user.iam_role_name}',
        '--set', f'toolsDomain={settings.TOOLS_DOMAIN}',
    )
