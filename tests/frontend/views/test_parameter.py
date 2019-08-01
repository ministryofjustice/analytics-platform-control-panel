from django.urls import reverse
from model_mommy import mommy
import pytest
from rest_framework import status


@pytest.fixture(autouse=True)
def users(users):
    users.update({
        'owner': mommy.make('api.User', username='owner'),
    })
    return users


@pytest.fixture(autouse=True)
def param(users):
    param = mommy.make('api.Parameter', created_by=users['owner'])
    return param


def list(client, *args):
    return client.get(reverse('list-parameters'))


def create(client, *args):
    data = {
        'key': 'test_key_1',
        'role_name': 'test_role',
        'app_type': 'webapp',
        'value': 'test_value',
    }
    return client.post(reverse('create-parameter'), data)


def delete(client, param, *args):
    return client.post(reverse('delete-parameter', kwargs={'pk': param.id}))


@pytest.mark.parametrize(
    'view,user,expected_status',
    [
        (list, 'superuser', status.HTTP_200_OK),
        (list, 'owner', status.HTTP_200_OK),
        (list, 'normal_user', status.HTTP_200_OK),

        (create, 'superuser', status.HTTP_302_FOUND),
        (create, 'owner', status.HTTP_302_FOUND),
        (create, 'normal_user', status.HTTP_302_FOUND),

        (delete, 'superuser', status.HTTP_302_FOUND),
        (delete, 'owner', status.HTTP_302_FOUND),
        (delete, 'normal_user', status.HTTP_404_NOT_FOUND),
    ],
)
def test_permission(client, param, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, param, users)
    assert response.status_code == expected_status

