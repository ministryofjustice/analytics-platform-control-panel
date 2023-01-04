# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.urls import reverse
from model_mommy import mommy  # noqa: F401
from rest_framework import status


@pytest.fixture(autouse=True)
def auth0():
    with patch("controlpanel.frontend.views.user.auth0"), patch(
        "controlpanel.api.models.user.auth0"
    ):
        yield auth0


def list(client, *args):
    return client.get(reverse("list-users"))


def delete(client, users, *args):
    kwargs = {"pk": users["other_user"].auth0_id}
    return client.post(reverse("delete-user", kwargs=kwargs))


def retrieve(client, users, *args):
    kwargs = {"pk": users["other_user"].auth0_id}
    return client.get(reverse("manage-user", kwargs=kwargs))


def set_admin(client, users, *args):
    data = {
        "is_superuser": True,
    }
    kwargs = {"pk": users["other_user"].auth0_id}
    return client.post(reverse("set-superadmin", kwargs=kwargs), data)


def reset_mfa(client, users, *args):
    kwargs = {"pk": users["other_user"].auth0_id}
    return client.post(reverse("reset-mfa", kwargs=kwargs))


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (list, "superuser", status.HTTP_200_OK),
        (list, "normal_user", status.HTTP_403_FORBIDDEN),
        (delete, "superuser", status.HTTP_302_FOUND),
        (delete, "normal_user", status.HTTP_403_FORBIDDEN),
        (delete, "other_user", status.HTTP_403_FORBIDDEN),
        (retrieve, "superuser", status.HTTP_200_OK),
        (retrieve, "normal_user", status.HTTP_403_FORBIDDEN),
        (retrieve, "other_user", status.HTTP_200_OK),
        (set_admin, "superuser", status.HTTP_302_FOUND),
        (set_admin, "normal_user", status.HTTP_403_FORBIDDEN),
        (set_admin, "other_user", status.HTTP_403_FORBIDDEN),
        (reset_mfa, "superuser", status.HTTP_302_FOUND),
        (reset_mfa, "normal_user", status.HTTP_403_FORBIDDEN),
        (reset_mfa, "other_user", status.HTTP_403_FORBIDDEN),
    ],
)
def test_permission(client, users, view, user, expected_status):
    for key, val in users.items():
        client.force_login(val)
    client.force_login(users[user])
    response = view(client, users)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "view,user,expected_count",
    [
        (list, "superuser", 3),
    ],
)
def test_list(client, users, view, user, expected_count):
    client.force_login(users[user])
    response = view(client, users)
    assert len(response.context_data["object_list"]) == expected_count


@pytest.yield_fixture
def slack():
    with patch("controlpanel.api.models.user.slack") as slack:
        yield slack


def test_grant_superuser_access(client, users, slack):
    request_user = users["superuser"]
    user = users["other_user"]
    client.force_login(request_user)
    response = set_admin(client, users)
    assert response.status_code == status.HTTP_302_FOUND
    slack.notify_superuser_created.assert_called_with(
        user.username,
        by_username=request_user.username,
    )
