from unittest.mock import call, patch

from django.conf import settings
from model_mommy import mommy
import pytest

from controlpanel.api.models import User


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


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


def test_helm_delete_user(helm):
    user = mommy.prepare('api.User')

    user.delete()

    helm.list_releases.assert_called_with(namespace=user.k8s_namespace)
    expected_calls = [
        call(helm.list_releases.return_value),
        call(f"init-user-{user.slug}"),
    ]
    helm.delete.has_calls(expected_calls)


def test_aws_create_role_calls_service(aws):
    user = User.objects.create(auth0_id="github|user_1")

    aws.create_user_role.assert_called_with(user)


def test_aws_delete_role_calls_service(aws):
    user = mommy.prepare('api.User')

    user.delete()

    aws.delete_role.assert_called_with(user.iam_role_name)


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
