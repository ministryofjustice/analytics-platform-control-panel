# Standard library
import json
from unittest.mock import patch

# Third-party
import pytest
from rest_framework import status
from rest_framework.reverse import reverse


def user_list(client, users):
    return client.get(reverse("user-list"))


def user_detail(client, users):
    return client.get(reverse("user-detail", (users["other_user"].auth0_id,)))


def user_own_detail(client, users):
    return client.get(reverse("user-detail", (users["normal_user"].auth0_id,)))


def user_delete(client, users):
    return client.delete(reverse("user-detail", (users["other_user"].auth0_id,)))


def user_delete_self(client, users):
    return client.delete(reverse("user-detail", (users["normal_user"].auth0_id,)))


def user_create(client, users):
    data = {
        "username": "foo",
        "auth0_id": "github|888",
        "email": "foo@example.com",
    }
    return client.post(
        reverse("user-list"),
        json.dumps(data),
        content_type="application/json",
    )


def user_update(client, users):
    data = {
        "username": "foo",
        "auth0_id": users["other_user"].auth0_id,
        "email": "foo@example.com",
        "is_admin": True,
    }
    return client.put(
        reverse("user-detail", (users["other_user"].auth0_id,)),
        json.dumps(data),
        content_type="application/json",
    )


def user_update_self(client, users):
    data = {"username": "foo", "auth0_id": users["normal_user"].auth0_id}
    return client.put(
        reverse("user-detail", (users["normal_user"].auth0_id,)),
        json.dumps(data),
        content_type="application/json",
    )


@pytest.fixture
def auth0():
    with patch("controlpanel.api.models.user.auth0") as auth0:
        yield auth0


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (user_list, "superuser", status.HTTP_200_OK),
        (user_detail, "superuser", status.HTTP_200_OK),
        (user_delete, "superuser", status.HTTP_204_NO_CONTENT),
        (user_create, "superuser", status.HTTP_201_CREATED),
        (user_update, "superuser", status.HTTP_200_OK),
        (user_list, "normal_user", status.HTTP_403_FORBIDDEN),
        (user_detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (user_own_detail, "superuser", status.HTTP_200_OK),
        (user_own_detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (user_delete, "normal_user", status.HTTP_403_FORBIDDEN),
        (user_delete_self, "normal_user", status.HTTP_403_FORBIDDEN),
        (user_create, "normal_user", status.HTTP_403_FORBIDDEN),
        (user_update, "normal_user", status.HTTP_403_FORBIDDEN),
        (user_update_self, "superuser", status.HTTP_200_OK),
        (user_update_self, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_permission(client, users, view, user, expected_status, auth0):
    client.force_login(users[user])
    response = view(client, users)
    assert response.status_code == expected_status
