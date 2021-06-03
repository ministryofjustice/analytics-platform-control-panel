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
            f"--set=EFSHostname={settings.EFS_HOSTNAME},"
            f"Username={user.slug},"
            f"Email={user.email},"
            f"Fullname={user.get_full_name()},"
            f"Env={settings.ENV},"
            f"OidcDomain={settings.OIDC_DOMAIN}"
            f'bootstrap-user-{user.slug}',
            'mojanalytics/bootstrap-user',
            f"--set=Username={user.slug}"
        ),
        call(
            f'bootstrap-user-{user.slug}',
            'mojanalytics/bootstrap-user',
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


def test_reset_home(helm, users):
    user = users['normal_user']
    cluster.User(user).reset_home()

    expected_calls = [
        call(
            f"reset-user-home-{user.slug}",
            f"mojanalytics/reset-user-home",
            f"--namespace=user-{user.slug}",
            f"--set=Username={user.slug}",
        ),
    ]
    helm.upgrade_release.assert_has_calls(expected_calls)


def test_delete(aws, helm, users):
    user = users['normal_user']
    cluster.User(user).delete()

    aws.delete_role.assert_called_with(user.iam_role_name)
    expected_calls = [
        call(helm.list_releases.return_value),
        call(f"init-user-{user.slug}"),
    ]
    helm.delete.assert_has_calls(expected_calls)


def test_delete_with_no_releases(aws, helm, users):
    """
    If there are no releases associated with the user, don't try to delete with
    an empty list of releases.
    """
    user = users['normal_user']
    helm.list_releases.return_value = []
    cluster.User(user).delete()

    aws.delete_role.assert_called_with(user.iam_role_name)
    helm.delete.assert_called_once_with(f"init-user-{user.slug}")
