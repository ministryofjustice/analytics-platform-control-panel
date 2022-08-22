from unittest.mock import call, patch

from django.conf import settings
from model_mommy import mommy
import pytest

from controlpanel.api.models import User
from controlpanel.api import cluster


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.yield_fixture
def auth0():
    with patch("controlpanel.api.models.user.auth0") as auth0:
        yield auth0


def test_helm_create_user(helm):
    user = mommy.prepare('api.User')

    expected_calls = [
        call(
            f'bootstrap-user-{user.slug}',
            'mojanalytics/bootstrap-user',
            f"--set=Username={user.slug}"
        ),
        call(
            f'provision-user-{user.slug}',
            'mojanalytics/provision-user',
            f'--namespace=user-{user.slug}',
            f"--set=Username={user.slug},",
            f"Efsvolume={settings.EFS_VOLUME}"
        ),
        call(
            f'config-user-{user.slug}',
            'mojanalytics/config-user',
            f'--namespace=user-{user.slug}',
            f'--set=Username={user.slug}',
        ),
    ]
    helm.upgrade_release.has_calls(expected_calls)


def test_helm_delete_user(helm, auth0):
    user = User.objects.create(username='bob', auth0_id="github|user_2")
    authz = auth0.ExtendedAuth0.return_value
    helm.list_releases.side_effect = [["chart-release", "provision-user-bob"],
                                      ["chart-release1", "bootstrap-user-bob"]]
    user.delete()
    helm.delete_eks.assert_has_calls(
        [call('user-bob', 'chart-release'),
         call('user-bob', 'provision-user-bob'),
         call('cpanel', 'bootstrap-user-bob')]
    )
    authz.clear_up_user.assert_called_with(user_id="github|user_2")


def test_aws_create_role_calls_service(aws):
    user = User.objects.create(auth0_id="github|user_1")

    aws.create_user_role.assert_called_with(user)


def test_aws_delete_role_calls_service(aws, auth0):
    user = User.objects.create(auth0_id="github|user_1")

    user.delete()
    authz = auth0.ExtendedAuth0.return_value
    aws.delete_role.assert_called_with(user.iam_role_name)
    authz.clear_up_user.assert_called_with(user_id="github|user_1")


def test_k8s_namespace():
    user = User(username='AlicE')
    assert user.k8s_namespace == 'user-alice'


@pytest.yield_fixture
def slack():
    with patch('controlpanel.api.models.user.slack') as slack:
        yield slack


def test_slack_notification_on_create_superuser(slack):
    user = User.objects.create(
        username='test-user',
        is_superuser=True,
    )

    slack.notify_superuser_created.assert_called_once_with(
        user.username,
        by_username=None,
    )


def test_slack_notification_on_grant_superuser_access(slack, users):
    user = users['normal_user']
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
    old_state = user.migration_state
    usernames = [user.username, ]
    new_state = User.PENDING
    User.bulk_migration_update(usernames, new_state)
    user = User.objects.get(username="bob")
    assert user.migration_state == new_state
