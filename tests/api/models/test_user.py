from unittest.mock import call, patch

from django.conf import settings
from model_mommy import mommy
import pytest

from controlpanel.api.models import User
from controlpanel.api.slack import (
    CREATE_SUPERUSER_MESSAGE,
    GRANT_SUPERUSER_ACCESS_MESSAGE,
)


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


def test_helm_create_user(helm):
    user = mommy.prepare('api.User')

    expected_calls = [
        call(
            f'init-user-{user.slug}',
            'mojanalytics/init-user',
            f"--set=NFSHostname={settings.NFS_HOSTNAME},"
            f"Username={user.slug},"
            f"Email={user.email},"
            f"Fullname={user.get_full_name()},"
            f"Env={settings.ENV},"
            f"OidcDomain={settings.OIDC_DOMAIN}"
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

    helm.list_releases.assert_called_with(f"--namespace=user-{user.slug}")
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


def test_slack_notification_on_create_superuser(settings, slack_WebClient):
    user = User.objects.create(
        username='test-user',
        is_superuser=True,
    )

    slack_WebClient.assert_called_with(token=settings.SLACK['api_token'])
    slack_WebClient.return_value.chat_postMessage.assert_called_with(
        as_user=False,
        username=f"Control Panel [{settings.ENV}]",
        channel=settings.SLACK["channel"],
        text=CREATE_SUPERUSER_MESSAGE.format(
            username=user.username,
        ),
    )
