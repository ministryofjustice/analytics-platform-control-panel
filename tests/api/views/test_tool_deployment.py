from unittest.mock import patch

from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse


@pytest.fixture
def tool(db):
    return mommy.make('api.Tool')


def test_create_when_invalid_tool_name(client, users):
    client.force_login(users['normal_user'])
    tool_name = 'unsupported-tool'
    response = client.post(reverse('deployment-list'), {"name": tool_name})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_when_valid_tool_name(client, tool, users):
    with patch("controlpanel.api.models.tool.cluster.ToolDeployment") as ToolDeployment:
        client.force_login(users["normal_user"])
        response = client.post(reverse("deployment-list"), {"name": tool.chart_name})
        assert response.status_code == status.HTTP_201_CREATED

        ToolDeployment.assert_called_once_with(users["normal_user"], tool)
        ToolDeployment.return_value.install.assert_called()
