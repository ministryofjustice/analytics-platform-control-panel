import json
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.reverse import reverse


def list(client, users):
    return client.get(reverse('user-list'))


def detail(client, users):
    return client.get(reverse('user-detail', (users["other_user"].auth0_id,)))


def own_detail(client, users):
    return client.get(reverse('user-detail', (users["normal_user"].auth0_id,)))


def delete(client, users):
    return client.delete(reverse('user-detail', (users["other_user"].auth0_id,)))


def delete_self(client, users):
    return client.delete(reverse('user-detail', (users["normal_user"].auth0_id,)))


def create(client, users):
    data = {'username': 'foo', 'auth0_id': 'github|888'}
    return client.post(reverse('user-list'), data)


def update(client, users):
    data = {'username': 'foo', 'auth0_id': 'github|888'}
    return client.put(
        reverse('user-detail', (users["other_user"].auth0_id,)),
        json.dumps(data),
        content_type="application/json",
    )


def update_self(client, users):
    data = {'username': 'foo', 'auth0_id': 'github|888'}
    return client.put(
        reverse('user-detail', (users["normal_user"].auth0_id,)),
        json.dumps(data),
        content_type="application/json",
    )


@pytest.mark.parametrize(
    'view,user,expected_status',
    [
        (list, "superuser", status.HTTP_200_OK),
        (list, "normal_user", status.HTTP_200_OK),
        (detail, "superuser", status.HTTP_200_OK),
        (detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (own_detail, "normal_user", status.HTTP_200_OK),
        (delete, "superuser", status.HTTP_204_NO_CONTENT),
        (delete, "normal_user", status.HTTP_403_FORBIDDEN),
        (delete_self, "normal_user", status.HTTP_403_FORBIDDEN),
        (create, "superuser", status.HTTP_201_CREATED),
        (create, "normal_user", status.HTTP_403_FORBIDDEN),
        (update, "superuser", status.HTTP_200_OK),
        (update, "normal_user", status.HTTP_403_FORBIDDEN),
        (update_self, "normal_user", status.HTTP_200_OK),
    ],
)
@pytest.mark.django_db
def test_permission(client, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, users)
    assert response.status_code == expected_status
