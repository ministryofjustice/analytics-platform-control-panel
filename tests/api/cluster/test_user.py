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
    helm.list_releases.return_value = ["chart-release"]
    with patch("controlpanel.api.aws.settings.EKS", True):
        cluster.User(user).delete()

    aws.delete_role.assert_called_with(user.iam_role_name)
    helm.delete_eks.assert_has_calls(
        [call("user-bob", "chart-release"),
         call("cpanel", "chart-release")]
    )


def test_delete_eks_with_no_releases(aws, helm, users):
    """
    If there are no releases associated with the user, don't try to delete with
    an empty list of releases. Helm 3 version.
    """
    user = users['normal_user']
    helm.list_releases.return_value = []
    with patch("controlpanel.api.aws.settings.EKS", True):
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
    with patch("controlpanel.api.aws.settings.EKS", True):
        user = cluster.User(user_model)
        user._init_user = MagicMock()
        user.on_authenticate()
        user._init_user.assert_called_once_with()
    updated_user_model = User.objects.get(username="bob")
    assert updated_user_model.migration_state == User.COMPLETE


def test_on_authenticate_eks_migrating_existing_user(aws, helm, users):
    """
    On EKS, if a migrating user is encountered, the expected user
    initialisation takes place.
    """
    user_model = users['normal_user']
    user_model.migration_state = User.PENDING  # the user is ready to migrate.
    init_helm_chart = f"init-user-{user_model.slug}"

    with patch("controlpanel.api.aws.settings.EKS", True):
        user = cluster.User(user_model)
        user._init_user = MagicMock()
        user.on_authenticate()
        user._init_user.assert_called_once_with()
        aws.migrate_user_role.assert_called_once_with(user_model)

    updated_user_model = User.objects.get(username="bob")
    assert updated_user_model.migration_state == User.COMPLETE


def test_on_authenticate_eks_migrated_user(aws, helm, users):
    """
    On EKS, if a migrated user logs in, they are NOT re-migrated by accident.
    """
    user_model = users['normal_user']
    user_model.migration_state = User.COMPLETE # the user is migrated.
    helm.list_releases.return_value = [
        f"bootstrap-user-{user_model.slug}",
        f"provision-user-{user_model.slug}",
    ]
    with patch("controlpanel.api.aws.settings.EKS", True):
        user = cluster.User(user_model)
        user._init_user = MagicMock()
        user.on_authenticate()
        assert user._init_user.call_count == 0
        assert aws.migrate_user_role.call_count == 0
        assert helm.delete.call_count == 0


def test_on_authenticate_eks_migrated_user_missing_charts(aws, helm, users):
    """
    On EKS, if a migrated user logs in, and they are missing their charts,
    these are recreated.
    """
    user_model = users['normal_user']
    user_model.migration_state = User.COMPLETE # the user is migrated.
    helm.list_releases.return_value = []
    with patch("controlpanel.api.aws.settings.EKS", True):
        user = cluster.User(user_model)
        user._init_user = MagicMock()
        user.on_authenticate()
        # The charts are recreated.
        assert user._init_user.call_count == 1
        # But other "migration" related events don't happen.
        assert aws.migrate_user_role.call_count == 0
        assert helm.delete.call_count == 0
