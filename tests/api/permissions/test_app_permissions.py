import json
from unittest.mock import patch

from model_mommy import mommy
import pytest
from rest_framework.reverse import reverse
from rest_framework import status


@pytest.fixture(autouse=True)
def app():
    return mommy.make("api.App", name="App 1")


@pytest.yield_fixture(autouse=True)
def mock_services():
    with patch('controlpanel.api.services.aws'):
        yield


def app_list(client, *args):
    return client.get(reverse('app-list'))


def app_detail(client, app, *args):
    return client.get(reverse('app-detail', (app.id,)))


def app_delete(client, app, *args):
    return client.delete(reverse('app-detail', (app.id,)))


def app_create(client, *args):
    data = {'name': 'test-app', 'repo_url': "https://example.com"}
    return client.post(reverse('app-list'), data)


def app_update(client, app, *args):
    data = {'name': 'test-app', 'repo_url': "https://example.com"}
    return client.put(
        reverse('app-detail', (app.id,)),
        json.dumps(data),
        content_type='application/json',
    )


@pytest.mark.parametrize(
    'view,user,expected_status',
    [
        (app_list, 'superuser', status.HTTP_200_OK),
        (app_detail, 'superuser', status.HTTP_200_OK),
        (app_delete, 'superuser', status.HTTP_204_NO_CONTENT),
        (app_create, 'superuser', status.HTTP_201_CREATED),
        (app_update, 'superuser', status.HTTP_200_OK),
        (app_list, 'normal_user', status.HTTP_200_OK),
        (app_detail, 'normal_user', status.HTTP_403_FORBIDDEN),
        (app_delete, 'normal_user', status.HTTP_403_FORBIDDEN),
        (app_create, 'normal_user', status.HTTP_403_FORBIDDEN),
        (app_update, 'normal_user', status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_permission(client, app, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, app)
    assert response.status_code == expected_status
