from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

import controlpanel.api.rules


@pytest.yield_fixture(autouse=True)
def mock_tool():
    with patch('controlpanel.api.views.tools.Tool'):
        yield


def deploy(client):
    return client.post(reverse('deployment-list'), {"name": 'rstudio'})


not_authenticated = None


@pytest.mark.parametrize(
    'view,user,expected_status',
    [
        (deploy, not_authenticated, status.HTTP_403_FORBIDDEN),
        (deploy, "normal_user", status.HTTP_201_CREATED),
        (deploy, "superuser", status.HTTP_201_CREATED),
    ],
)
@pytest.mark.django_db
def test_permission(client, users, view, user, expected_status):
    if user:
        user = users[user]
        client.force_login(user)
    response = view(client)
    assert response.status_code == expected_status
