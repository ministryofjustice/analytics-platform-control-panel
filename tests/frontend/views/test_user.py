# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.urls import reverse
from rest_framework import status

# First-party/Local
from controlpanel.api import cluster


@pytest.fixture(autouse=True)
def auth0():
    with patch("controlpanel.api.models.user.auth0"):
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


def set_bedrock(client, users, *args):
    data = {
        "is_bedrock_enabled": True,
    }
    kwargs = {"pk": users["other_user"].auth0_id}
    return client.post(reverse("set-bedrock", kwargs=kwargs), data)


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
        (set_bedrock, "superuser", status.HTTP_302_FOUND),
        (set_bedrock, "normal_user", status.HTTP_403_FORBIDDEN),
        (set_bedrock, "other_user", status.HTTP_403_FORBIDDEN),
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


@pytest.fixture
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


@pytest.mark.parametrize(
    "data, action",
    [
        ({"enable_quicksight": True}, "attach"),
        ({}, "remove"),
    ],
    ids=["enable", "disable"],
)
@patch("controlpanel.api.models.user.cluster.User.update_policy_attachment")
def test_enable_quicksight_access(update_policy_attachment, data, action, client, users):
    request_user = users["superuser"]
    user = users["other_user"]
    url = reverse("set-quicksight", kwargs={"pk": user.auth0_id})

    client.force_login(request_user)
    response = client.post(url, data=data)

    assert response.status_code == status.HTTP_302_FOUND
    update_policy_attachment.assert_called_once_with(
        policy=cluster.User.QUICKSIGHT_POLICY_NAME,
        action=action,
    )
