from django.urls import reverse
from model_mommy import mommy
import pytest
from rest_framework import status
from unittest.mock import patch


@pytest.fixture(autouse=True)
def users(users):
    users.update({
        'owner': mommy.make('api.User', username='owner'),
    })
    return users


@pytest.fixture(autouse=True)
def param(users):
    with patch('controlpanel.api.aws.AWSParameterStore.create_parameter') as create_parameter:
        mommy.make('api.Parameter', 3, created_by=users['other_user'])
        param = mommy.make('api.Parameter', created_by=users['owner'])
        return param


def list(client, *args):
    return client.get(reverse('list-parameters'))


def list_all(client, *args):
    return client.get(reverse('list-all-parameters'))


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

        (list_all, 'superuser', status.HTTP_200_OK),
        (list_all, 'owner', status.HTTP_403_FORBIDDEN),
        (list_all, 'normal_user', status.HTTP_403_FORBIDDEN),

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


@pytest.mark.parametrize(
    'view,user,expected_count',
    [
        (list, 'superuser', 0),
        (list, 'normal_user', 0),
        (list, 'owner', 1),
        (list, 'other_user', 3),

        (list_all, 'superuser', 4),
    ],
)
def test_list(client, param, users, view, user, expected_count):
    client.force_login(users[user])
    response = view(client, param, users)
    assert len(response.context_data['object_list']) == expected_count

