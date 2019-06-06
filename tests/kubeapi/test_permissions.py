from unittest.mock import MagicMock, patch

from model_mommy import mommy
import pytest
from rest_framework import status


TEST_K8S_API_URL = 'https://k8s.example.com'


@pytest.yield_fixture(autouse=True)
def k8s():
    with patch('controlpanel.kubeapi.views.kubernetes') as k8s:
        config = k8s.client.Configuration.return_value
        config.host = TEST_K8S_API_URL
        config.api_key = {
            "authorization": "Bearer test-token",
        }
        yield k8s


@pytest.yield_fixture(autouse=True)
def k8s_api():
    with patch('djproxy.views.request') as request:
        request.return_value.status_code = 200
        yield request


@pytest.fixture
def users():
    return {
        "superuser": mommy.make(
            'api.User',
            auth0_id='github|0',
            is_superuser=True,
            username='alice',
        ),
        "normal_user": mommy.make(
            'api.User',
            username='bob',
            auth0_id='github|1',
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
def test_permission(client, users, view, user, expected_status):
    print('start', flush=True)
    if user:
        user = users[user]
        client.force_login(user)
    print('getting view', flush=True)
    response = view(client, user)
    print('got response', flush=True)
    assert response.status_code == expected_status
