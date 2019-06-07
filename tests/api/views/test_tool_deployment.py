from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from controlpanel.api.tools import Tool


@pytest.fixture(autouse=True)
def logged_in_normal_user(client, users):
    client.force_login(users[1])
    return users[1]


@pytest.yield_fixture(autouse=True)
def tool_deploy():
    with patch.object(Tool, 'deploy_for') as deploy:
        yield deploy


def test_create_when_invalid_tool_name(client):
    tool_name = 'unsupported-tool'
    response = client.post(reverse('deployment-list'), {"name": tool_name})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_when_valid_tool_name(client, tool_deploy, logged_in_normal_user):
    tool_name = 'rstudio'
    response = client.post(reverse('deployment-list'), {"name": tool_name})
    assert response.status_code == status.HTTP_201_CREATED

    tool_deploy.assert_called_with(logged_in_normal_user)
