# Standard library
from unittest.mock import MagicMock, call, patch

# Third-party
import pytest

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models.user import User


def test_iam_role_name(users):
    assert cluster.User(users["normal_user"]).iam_role_name == "test_user_bob"


def test_create(helm, settings, users):
    with patch("controlpanel.api.cluster.AWSRole.create_role") as aws_create_role:
        user = users["normal_user"]
        cluster.User(user).create()
        aws_create_role.assert_called_with(
            user.iam_role_name,
            cluster.User.aws_user_policy(user.auth0_id, user.slug),
            cluster.User.ATTACH_POLICIES,
        )
        expected_calls = [
            call(
                f"bootstrap-user-{user.slug}",
                "mojanalytics/bootstrap-user",
                f"--namespace=user-{user.slug}",
                f"--set=Username={user.slug},",
                f"Efsvolume={settings.EFS_VOLUME}",
            ),
            call(
                f"config-user-{user.slug}",
                "mojanalytics/config-user",
                f"--namespace=user-{user.slug}",
                f"--set=Username={user.slug}",
            ),
        ]
        helm.upgrade_release.has_calls(expected_calls)


def test_reset_home(helm, users):
    user = users["normal_user"]
    cluster.User(user).reset_home()

    expected_calls = [
        call(
            f"reset-user-efs-home-{user.slug}",
            "mojanalytics/reset-user-efs-home",
            f"--namespace=user-{user.slug}",
            f"--set=Username={user.slug}",
        ),
    ]
    helm.upgrade_release.assert_has_calls(expected_calls)


@pytest.yield_fixture
def aws_delete_role():
    with patch(
        "controlpanel.api.cluster.AWSRole.delete_role"
    ) as aws_delete_role_action:
        yield aws_delete_role_action


def test_delete(aws_delete_role, helm, users):
    """
    Delete with Helm 3.
    """
    user = users["normal_user"]
    helm.list_releases.return_value = [
        "chart-release",
    ]
    cluster.User(user).delete()
    aws_delete_role.assert_called_with(user.iam_role_name)
    expected_calls = [
        call(f"user-{user.slug}", "chart-release"),
        call("cpanel", "chart-release"),
    ]
    helm.delete.has_calls(expected_calls)


def test_delete_eks_with_no_releases(aws_delete_role, helm, users):
    """
    If there are no releases associated with the user, don't try to delete with
    an empty list of releases. Helm 3 version.
    """
    user = users["normal_user"]
    helm.list_releases.return_value = []
    cluster.User(user).delete()

    aws_delete_role.assert_called_with(user.iam_role_name)
    assert not helm.delete.called


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
    user_model = users["normal_user"]
    user_model.migration_state = User.VOID
    user = cluster.User(user_model)
    user._init_user = MagicMock()
    user.on_authenticate()
    user._init_user.assert_called_once_with()


def test_on_authenticate_user_missing_charts(helm, users):
    """
    On EKS, if a migrated user logs in, and they are missing their charts,
    these are recreated.
    """
    user_model = users["normal_user"]
    user_model.migration_state = User.COMPLETE  # the user is migrated.
    helm.list_releases.return_value = []
    user = cluster.User(user_model)
    user._init_user = MagicMock()
    user.on_authenticate()
    # The charts are recreated.
    assert user._init_user.call_count == 1
    assert helm.delete.call_count == 0
