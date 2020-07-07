from unittest.mock import call

import pytest

from controlpanel.api import cluster


def test_iam_role_name(users):
    assert cluster.User(users['normal_user']).iam_role_name == 'test_user_bob'


def test_create(aws, helm, settings, users):
    user = users['normal_user']
    cluster.User(user).create()

    aws.create_user_role.assert_called_with(user)
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


def test_reset_home(helm, users):
    user = users['normal_user']
    cluster.User(user).reset_home()

    expected_calls = [
        call(
            f'reset-user-{user.slug}',
            'mojanalytics/reset-user',
            f'--namespace=user-{user.slug}',
            f'--set=Username={user.slug}',
        ),
    ]
    helm.reset_home.assert_has_calls(expected_calls)


def test_delete(aws, helm, users):
    user = users['normal_user']
    cluster.User(user).delete()

    aws.delete_role.assert_called_with(user.iam_role_name)
    expected_calls = [
        call(helm.list_releases.return_value),
        call(f"init-user-{user.slug}"),
    ]
    helm.delete.assert_has_calls(expected_calls)

