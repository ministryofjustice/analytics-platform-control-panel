# Standard library
from unittest.mock import call, patch

# Third-party
import pytest

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import User


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def auth0():
    with patch("controlpanel.api.models.user.auth0") as auth0:
        yield auth0


def test_helm_delete_user(helm, auth0):
    user = User.objects.create(username="bob", auth0_id="github|user_2")
    authz = auth0.ExtendedAuth0.return_value
    helm.list_releases.side_effect = [
        ["chart-release", "provision-user-bob"],
        ["chart-release1", "bootstrap-user-bob"],
    ]
    user.delete()
    helm.delete.assert_has_calls(
        [
            call("user-bob", "chart-release", dry_run=False),
            call("user-bob", "provision-user-bob", dry_run=False),
            call("cpanel", "bootstrap-user-bob", dry_run=False),
        ]
    )
    authz.clear_up_user.assert_called_with(user_id="github|user_2")


def test_aws_create_role_calls_service():
    with patch("controlpanel.api.cluster.AWSRole.create_role") as create_user_role:
        user = User.objects.create(auth0_id="github|user_1")
        create_user_role.assert_called_with(
            user.iam_role_name,
            cluster.User.aws_user_policy(user.auth0_id, user.slug),
            cluster.User.ATTACH_POLICIES,
        )


def test_aws_delete_role_calls_service(auth0):
    with patch("controlpanel.api.cluster.AWSRole.delete_role") as aws_delete_role:
        user = User.objects.create(auth0_id="github|user_1")

        user.delete()
        authz = auth0.ExtendedAuth0.return_value
        aws_delete_role.assert_called_with(user.iam_role_name)
        authz.clear_up_user.assert_called_with(user_id="github|user_1")


def test_k8s_namespace():
    user = User(username="AlicE")
    assert user.k8s_namespace == "user-alice"


@pytest.fixture
def slack():
    with patch("controlpanel.api.models.user.slack") as slack:
        yield slack


def test_slack_notification_on_create_superuser(slack):
    user = User.objects.create(
        username="test-user",
        is_superuser=True,
    )

    slack.notify_superuser_created.assert_called_once_with(
        user.username,
        by_username=None,
    )


def test_slack_notification_on_grant_superuser_access(slack, users):
    user = users["normal_user"]
    user.is_superuser = True
    user.save()

    slack.notify_superuser_created.assert_called_with(
        user.username,
        by_username=None,
    )


def test_bulk_migration_update(users):
    """
    Given a list of users, check the bulk_migration_update results in the
    expected new migration state.
    """
    user = User.objects.get(username="bob")
    # old_state = user.migration_state
    usernames = [
        user.username,
    ]
    new_state = User.PENDING
    User.bulk_migration_update(usernames, new_state)
    user = User.objects.get(username="bob")
    assert user.migration_state == new_state


@pytest.mark.parametrize("enable", [True, False], ids=["enable", "disable"])
def test_set_quicksight_access(users, enable):

    user = users["other_user"]
    with patch.object(cluster.User, "update_policy_attachment") as mock_update_policy_attachment:
        user.set_quicksight_access(enable=enable)
        mock_update_policy_attachment.assert_called_once_with(
            policy=cluster.User.QUICKSIGHT_POLICY_NAME,
            attach=enable,
        )


@pytest.mark.parametrize(
    "auth0_id, expected",
    [
        ("github|user_1", True),
        ("github|user_2", True),
        ("entra|user_1", False),
        ("other|user_2", False),
    ],
)
def test_user_is_iam_user(auth0_id, expected):
    user = User(auth0_id=auth0_id)
    assert user.is_iam_user == expected


def test_non_github_user_not_provisioned():
    user = User.objects.create(auth0_id="not_github|user_1")
    with patch.object(cluster.User, "create") as mock_create:
        user.save()
        mock_create.assert_not_called()
