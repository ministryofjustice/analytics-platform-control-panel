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
                "--namespace=cpanel",
                f"--set=Username={user.slug}",
            ),
            call(
                f"provision-user-{user.slug}",
                "mojanalytics/provision-user",
                f"--namespace=user-{user.slug}",
                (
                    f"--set=Username={user.slug},Efsvolume={settings.EFS_VOLUME},"
                    "OidcDomain=oidc.idp.example.com,Email=,Fullname="
                ),
            ),
        ]

        helm.upgrade_release.assert_has_calls(expected_calls)


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


@pytest.fixture
def aws_delete_role():
    with patch("controlpanel.api.cluster.AWSRole.delete_role") as aws_delete_role_action:
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
        call("user-bob", "chart-release", dry_run=False),
    ]
    helm.delete.assert_has_calls(expected_calls)


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


@pytest.mark.parametrize(
    "attach, method", [(True, "attach_policy"), (False, "remove_policy")], ids=["attach", "remove"]
)
def test_update_policy_attachment(users, attach, method):
    user = cluster.User(users["normal_user"])
    with patch.object(user.aws_role_service, method) as mock:
        user.update_policy_attachment("policy_name", attach=attach)
        mock.assert_called_once_with(user.iam_role_name, ["policy_name"])


def test_has_policy_attached(users):
    user = cluster.User(users["normal_user"])
    with patch.object(user.aws_role_service, "list_attached_policies") as mock:
        mock.return_value = [MagicMock(policy_name="expected_policy")]
        assert user.has_policy_attached("expected_policy") is True
        assert user.has_policy_attached("unexpected_policy") is False
