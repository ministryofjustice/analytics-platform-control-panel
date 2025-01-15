# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.urls import reverse
from rest_framework import status

# First-party/Local
from controlpanel.api import aws, cluster


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
        (list, "superuser", 9),
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


@patch.object(aws.AWSIdentityStore, "get_group_membership_id")
@patch.object(aws.AWSIdentityStore, "get_user_id")
def test_grant_superuser_access(
    get_user_id,
    get_group_membership_id,
    identity_store_user_setup,
    identity_store,
    identity_store_id,
    group_ids,
    client,
    users,
    slack,
):
    request_user = users["superuser"]
    user = users["other_user"]
    get_user_id.return_value = user.identity_center_id
    get_group_membership_id.side_effect = [None, None]
    client.force_login(request_user)
    response = set_admin(client, users)
    assert response.status_code == status.HTTP_302_FOUND
    slack.notify_superuser_created.assert_called_with(
        user.username,
        by_username=request_user.username,
    )

    response = identity_store.list_group_memberships_for_member(
        IdentityStoreId=identity_store_id,
        MemberId={"UserId": user.identity_center_id},
    )

    assert len(response["GroupMemberships"]) == 2
    expected_groups = ["quicksight_compute_author", "azure_holding"]

    groups = [group_ids[group] for group in expected_groups]

    for group_membership in response["GroupMemberships"]:
        if group_membership["GroupId"] not in groups:
            raise AssertionError


@pytest.mark.parametrize(
    "data, legacy_access",
    [
        ({"enable_quicksight": ["quicksight_legacy"]}, True),
        ({}, False),
    ],
    ids=["legacy enabled", "no access"],
)
@patch("controlpanel.api.models.user.cluster.User.update_policy_attachment")
def test_enable_quicksight_access_legacy(
    update_policy_attachment, data, legacy_access, client, users
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


@patch.object(aws.AWSIdentityStore, "get_group_membership_id")
@patch.object(aws.AWSIdentityStore, "get_user_id")
@pytest.mark.parametrize(
    "user, data, group_membership_calls, expected_groups, expected_result",
    [
        (
            "superuser",
            {"enable_quicksight": ["quicksight_compute_reader"]},
            [None, "Mock-Azure-Holding-Id"],
            ["quicksight_compute_author", "azure_holding"],
            2,
        ),
        (
            "normal_user",
            {"enable_quicksight": ["quicksight_compute_reader"]},
            [None, None],
            ["quicksight_compute_reader", "azure_holding"],
            2,
        ),
        (
            "superuser",
            {"enable_quicksight": ["quicksight_compute_author"]},
            ["Mock-Author-Id", "Mock-Azure-Holding-Id"],
            ["quicksight_compute_author", "azure_holding"],
            2,
        ),
        (
            "normal_user",
            {"enable_quicksight": ["quicksight_compute_author"]},
            [None, None],
            ["quicksight_compute_author", "azure_holding"],
            2,
        ),
        (
            "normal_user",
            {"enable_quicksight": ["quicksight_compute_author", "quicksight_compute_reader"]},
            [None, None, None, "Mock-Azure-Holding-Id"],
            ["quicksight_compute_author", "quicksight_compute_reader", "azure_holding"],
            3,
        ),
        (
            "quicksight_compute_reader",
            {"enable_quicksight": ["quicksight_compute_reader"]},
            ["insert-membership-id", "Mock-Azure-Holding-Id"],
            ["quicksight_compute_reader", "azure_holding"],
            2,
        ),
    ],
)
def test_quicksight_form_add_to_groups(
    get_user_id,
    get_group_membership_id,
    identity_store_user_setup,
    users,
    identity_store,
    identity_store_id,
    client,
    group_ids,
    user,
    data,
    group_membership_calls,
    expected_groups,
    expected_result,
):
    """
    Tests adding a user to the correct group plus the azure holding group.
    Super users should not be added to these groups as they should already be in them
    """

    test_user = users[user]
    get_user_id.return_value = test_user.identity_center_id

    for i in range(len(group_membership_calls)):
        if group_membership_calls[i] == "insert-membership-id":
            group_membership_calls[i] = test_user.group_membership_id

    get_group_membership_id.side_effect = group_membership_calls

    request_user = users["superuser"]
    url = reverse("set-quicksight", kwargs={"pk": test_user.auth0_id})

    client.force_login(request_user)
    response = client.post(url, data=data)
    assert response.status_code == status.HTTP_302_FOUND

    response = identity_store.list_group_memberships_for_member(
        IdentityStoreId=identity_store_id,
        MemberId={"UserId": test_user.identity_center_id},
    )

    assert len(response["GroupMemberships"]) == expected_result

    groups = [group_ids[group] for group in expected_groups]

    for group_membership in response["GroupMemberships"]:
        if group_membership["GroupId"] not in groups:
            raise AssertionError


@patch.object(aws.AWSIdentityStore, "get_group_membership_id")
@patch.object(aws.AWSIdentityStore, "get_user_id")
@pytest.mark.parametrize(
    "user, data, expected_result",
    [
        (
            "quicksight_compute_author",
            {"enable_quicksight": []},
            1,
        ),
        (
            "quicksight_compute_reader",
            {"enable_quicksight": []},
            1,
        ),
        (
            "normal_user",
            {"enable_quicksight": []},
            0,
        ),
    ],
)
def test_quicksight_form_remove_from_group(
    get_user_id,
    get_group_membership_id,
    identity_store_user_setup,
    client,
    users,
    identity_store,
    identity_store_id,
    group_ids,
    user,
    data,
    expected_result,
):
    """
    Tests removing a user from their group.
    Should still be part of azure holding group if already in a group
    """

    test_user = users[user]
    get_user_id.return_value = test_user.identity_center_id
    get_group_membership_id.return_value = (
        test_user.group_membership_id if expected_result > 0 else None
    )
    request_user = users["superuser"]
    url = reverse("set-quicksight", kwargs={"pk": test_user.auth0_id})

    client.force_login(request_user)
    response = client.post(url, data=data)
    assert response.status_code == status.HTTP_302_FOUND

    response = identity_store.list_group_memberships_for_member(
        IdentityStoreId=identity_store_id,
        MemberId={"UserId": test_user.identity_center_id},
    )

    assert len(response["GroupMemberships"]) == expected_result

    if expected_result > 0:
        assert response["GroupMemberships"][0]["GroupId"] == group_ids["azure_holding"]
