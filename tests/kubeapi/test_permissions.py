from unittest.mock import patch

from model_mommy import mommy
import pytest
from rest_framework import status


@pytest.yield_fixture()
def mock_k8s_api():
    with patch('djproxy.views.request') as request:
        request.return_value.status_code = 200
        yield request


@pytest.fixture
def users():
    return {
        "superuser": mommy.make(
            'api.User',
            auth0_id='github|user_1',
            is_superuser=True,
        ),
        "normal_user": mommy.make(
            'api.User',
            username='alice',
            auth0_id='github|user_2',
            is_superuser=False,
        ),
    }


def anything(client, user):
    return client.get('/api/k8s/anything')


def outside_own_namespace(client, user):
    return client.get('/api/k8s/api/v1/namespaces/user-other/')


def inside_own_namespace(client, user):
    return client.get(f'/api/k8s/api/v1/namespaces/user-{user.username.lower()}/')


def disallowed_api(client, user):
    disallowed_api = 'apis/disallowed/v1alpha0'
    username = user.username.lower()
    return client.get(f'/api/k8s/{disallowed_api}/namespaces/user-{username}/')


def namespace_with_same_prefix(client, user):
    username = user.username.lower()
    other_username = f'{username}other'
    return client.get(f'/api/k8s/api/v1/namespaces/user-{other_username}/anything')


not_authenticated = None


@pytest.mark.parametrize(
    'view,user,expected_status',
    [
        (anything, not_authenticated, status.HTTP_403_FORBIDDEN),
        (anything, "superuser", status.HTTP_200_OK),
        (outside_own_namespace, "normal_user", status.HTTP_403_FORBIDDEN),
        (inside_own_namespace, "normal_user", status.HTTP_200_OK),
        (disallowed_api, "normal_user", status.HTTP_403_FORBIDDEN),
        (namespace_with_same_prefix, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_permission(
        client, users, mock_k8s_api, view, user, expected_status):
    if user:
        user = users[user]
        client.force_login(user)
    response = view(client, user)
    assert response.status_code == expected_status
