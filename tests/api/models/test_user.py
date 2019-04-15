from unittest.mock import call, patch

from django.conf import settings
from model_mommy import mommy
import pytest

from controlpanel.api.models import User
from controlpanel.api.services import READ_INLINE_POLICIES_POLICY_NAME
from tests.api import USER_IAM_ROLE_ASSUME_POLICY


@pytest.yield_fixture
def helm():
    with patch('controlpanel.api.models.helm') as helm:
        yield helm


@pytest.yield_fixture
def aws():
    with patch('controlpanel.api.services.aws') as aws:
        yield aws


def test_helm_create_user(helm):
    user = mommy.prepare('api.User')

    user.helm_create()

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

    user.helm_delete()

    helm.list_releases.assert_called_with(f"--namespace=user-{user.slug}")
    expected_calls = [
        call(helm.list_releases.return_value),
        call(f"init-user-{user.slug}"),
    ]
    helm.delete.has_calls(expected_calls)


def test_aws_create_role_calls_service(aws):
    user = mommy.prepare('api.User', auth0_id="github|user_1")

    user.aws_create_role()

    aws.create_role.assert_called_with(
        user.iam_role_name,
        USER_IAM_ROLE_ASSUME_POLICY,
    )
    aws.attach_policy_to_role.assert_called_with(
        role_name=user.iam_role_name,
        policy_arn=f"{settings.IAM_ARN_BASE}:policy/{READ_INLINE_POLICIES_POLICY_NAME}",
    )


def test_aws_delete_role_calls_service(aws):
    user = mommy.prepare('api.User')

    user.aws_delete_role()

    aws.delete_role.assert_called_with(user.iam_role_name)


def test_k8s_namespace():
    user = User(username='AlicE')
    assert user.k8s_namespace == 'user-alice'
