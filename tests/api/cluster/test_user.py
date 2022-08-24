from unittest.mock import call, patch, MagicMock

import pytest

from controlpanel.api import cluster
from controlpanel.api.models.user import User


def test_iam_role_name(users):
    assert cluster.User(users['normal_user']).iam_role_name == 'test_user_bob'


def test_create(aws, helm, settings, users):
    user = users['normal_user']
    cluster.User(user).create()

    aws.create_user_role.assert_called_with(user)
    expected_calls = [
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
            f"reset-user-efs-home-{user.slug}",
            f"mojanalytics/reset-user-efs-home",
            f"--namespace=user-{user.slug}",
            f"--set=Username={user.slug}",
        ),
    ]
    helm.upgrade_release.assert_has_calls(expected_calls)


def test_delete_eks(aws, helm, users):
    """
    Delete with Helm 3.
    """
    user = users['normal_user']
    helm.list_releases.return_value = ["chart-release", ]
    cluster.User(user).delete()

    aws.delete_role.assert_called_with(user.iam_role_name)
    expected_calls = [
        call(f"user-{user.slug}", 'chart-release'),
        call("cpanel", 'chart-release'),
    ]
    helm.delete_eks.has_calls(expected_calls)


def test_delete_eks_with_no_releases(aws, helm, users):
    """
    If there are no releases associated with the user, don't try to delete with
    an empty list of releases. Helm 3 version.
    """
    user = users['normal_user']
    helm.list_releases.return_value = []
    cluster.User(user).delete()

    aws.delete_role.assert_called_with(user.iam_role_name)
    assert not helm.delete_eks.called


def test_on_authenticate(helm, users):
    """
    If not on EKS, check if the user has an init-user chart, if not, run it.
    """
    user_model = users["normal_user"]
    helm.list_releases.return_value = []
    user = cluster.User(user_model)
    user._init_user = MagicMock()
    user.on_authenticate()
    user._init_user.assert_called_once_with()


def test_on_authenticate_eks_completely_new_user(helm, users):
    """
    On EKS, if a completely (non-migrating) user is encountered, the expected
    user initialisation takes place.
    """
    user_model = users['normal_user']
    user_model.migration_state = User.VOID
    user = cluster.User(user_model)
    user._init_user = MagicMock()
    user.on_authenticate()
    user._init_user.assert_called_once_with()


def test_on_authenticate_user_missing_charts(aws, helm, users):
    """
    On EKS, if a migrated user logs in, and they are missing their charts,
    these are recreated.
    """
    user_model = users['normal_user']
    user_model.migration_state = User.COMPLETE # the user is migrated.
    helm.list_releases.return_value = []
    user = cluster.User(user_model)
    user._init_user = MagicMock()
    user.on_authenticate()
    # The charts are recreated.
    assert user._init_user.call_count == 1
    assert helm.delete_eks.call_count == 0
