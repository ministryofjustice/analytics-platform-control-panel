from unittest.mock import patch

from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse


@pytest.yield_fixture(autouse=True)
def deploy_tool():
    with patch('controlpanel.api.models.tool.cluster.deploy_tool') as deploy:
        yield deploy


@pytest.fixture
def tool(db):
    return mommy.make('api.Tool')


def test_create_when_invalid_tool_name(client, users):
    client.force_login(users['normal_user'])
    tool_name = 'unsupported-tool'
    response = client.post(reverse('deployment-list'), {"name": tool_name})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_when_valid_tool_name(client, deploy_tool, tool, users):
    client.force_login(users['normal_user'])
    response = client.post(reverse('deployment-list'), {"name": tool.chart_name})
    assert response.status_code == status.HTTP_201_CREATED

    deploy_tool.assert_called_with(tool, users['normal_user'])
