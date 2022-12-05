from unittest.mock import patch, MagicMock

from django.conf import settings
from model_mommy import mommy
import pytest

from controlpanel.api.models import Tool, ToolDeployment, User, HomeDirectory


@pytest.fixture
def tool(db):
    return mommy.make("api.Tool")


def test_deploy_for_generic(helm, tool, users):
    user = users["normal_user"]

    # simulate release with old naming scheme installed
    old_release_name = f"{tool.chart_name}-{user.username}"
    helm.list_releases.return_value = [old_release_name]

    tool_deployment = ToolDeployment(tool, user)
    tool_deployment.save()

    # uninstall tool with old naming scheme
    helm.delete.assert_called_with(user.k8s_namespace, old_release_name)

    # install new release
    helm.upgrade_release.assert_called_with(
        f"{tool.chart_name}-{user.slug}",
        f"mojanalytics/{tool.chart_name}",
        "--version",
        tool.version,
        "--namespace",
        user.k8s_namespace,
        "--set",
        f"username={user.username}",
        "--set",
        f"Username={user.username}",
        "--set",
        f"aws.iamRole={user.iam_role_name}",
        "--set",
        f"toolsDomain={settings.TOOLS_DOMAIN}",
    )


@pytest.yield_fixture
def cluster():
    with patch("controlpanel.api.models.tool.cluster") as cluster:
        yield cluster


@pytest.mark.django_db
@pytest.mark.parametrize(
    "chart_version, expected_description",
    [
        ("unknown-version", ''),
        ("1.0.0", ''),
        ("2.2.5", "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"),
    ],
    ids=["unknown-version", "chart-with-no-appVersion", "chart-with-appVersion",],
)
def test_tool_description_from_helm_chart(helm_repository_index, chart_version, expected_description):
    tool = Tool(chart_name="rstudio", version=chart_version).save()

    assert tool.description == expected_description


def test_home_directory_reset(cluster):
    user = User(username="test-user")
    hd = HomeDirectory(user)
    hd.reset()
    assert hd._subprocess == cluster.User(user).reset_home()


def test_home_directory_get_status():
    user = User(username="test-user")
    hd = HomeDirectory(user)
    cluster.HOME_RESETTING = "Resetting"
    hd._poll = MagicMock(return_value=cluster.HOME_RESETTING)
    hd._subprocess = True
    assert hd.get_status() == cluster.HOME_RESETTING
