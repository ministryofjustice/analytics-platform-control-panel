# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.urls import reverse
from rest_framework import status

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import QUICKSIGHT_EMBED_PERMISSION


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
    return client.post(reverse("set-bedrock-user", kwargs=kwargs), data)


def set_quicksight(client, users, *args):
    kwargs = {"pk": users["other_user"].auth0_id}
    return client.post(reverse("set-quicksight", kwargs=kwargs))


def reinitialise_user(client, users, *args):
    kwargs = {"pk": users["other_user"].auth0_id}
    return client.post(reverse("reinit-user", kwargs=kwargs))


def set_database_admin(client, users, *args):
    data = {
        "is_database_admin": True,
    }
    kwargs = {"pk": users["other_user"].auth0_id}
    return client.post(reverse("set-database-admin", kwargs=kwargs), data)


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
        (set_quicksight, "superuser", status.HTTP_302_FOUND),
        (set_quicksight, "normal_user", status.HTTP_403_FORBIDDEN),
        (set_quicksight, "other_user", status.HTTP_403_FORBIDDEN),
        (set_database_admin, "superuser", status.HTTP_302_FOUND),
        (set_database_admin, "normal_user", status.HTTP_403_FORBIDDEN),
        (set_database_admin, "other_user", status.HTTP_403_FORBIDDEN),
        (reinitialise_user, "superuser", status.HTTP_302_FOUND),
        (reinitialise_user, "normal_user", status.HTTP_403_FORBIDDEN),
        (reinitialise_user, "other_user", status.HTTP_403_FORBIDDEN),
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
        (list, "superuser", 5),
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
    "data, legacy_access, compute_access",
    [
        ({"enable_quicksight": ["quicksight_legacy"]}, True, False),
        ({"enable_quicksight": ["quicksight_compute"]}, False, True),
        ({"enable_quicksight": ["quicksight_legacy", "quicksight_compute"]}, True, True),
        ({}, False, False),
    ],
    ids=["legacy enabled", "compute enabled", "both enabled", "no access"],
)
@patch("controlpanel.api.models.user.cluster.User.update_policy_attachment")
def test_enable_quicksight_access(
    update_policy_attachment, data, legacy_access, compute_access, client, users
):
    request_user = users["superuser"]
    user = users["other_user"]
    url = reverse("set-quicksight", kwargs={"pk": user.auth0_id})

    client.force_login(request_user)
    response = client.post(url, data=data)

    assert response.status_code == status.HTTP_302_FOUND
    update_policy_attachment.assert_called_once_with(
        policy=cluster.User.QUICKSIGHT_POLICY_NAME,
        attach=legacy_access,
    )
    assert (
        user.user_permissions.filter(codename=QUICKSIGHT_EMBED_PERMISSION).exists()
        is compute_access
    )
