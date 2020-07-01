from unittest.mock import patch

from django.conf import settings
from model_mommy import mommy
import pytest

from controlpanel.api.models import Tool, ToolDeployment, User


@pytest.fixture
def tool(db):
    return mommy.make("api.Tool")


@pytest.yield_fixture
def token_hex():
    with patch("controlpanel.api.models.tool.secrets") as secrets:
        yield secrets.token_hex


def test_deploy_for_generic(helm, token_hex, tool, users):
    cookie_secret_proxy = "cookie secret proxy"
    cookie_secret_tool = "cookie secret tool"
    token_hex.side_effect = [cookie_secret_proxy, cookie_secret_tool]
    user = users["normal_user"]

    # simulate release with old naming scheme installed
    old_release_name = f"{user.username}-{tool.chart_name}"
    helm.list_releases.return_value = [old_release_name]

    tool_deployment = ToolDeployment(tool, user)
    tool_deployment.save()

    # uninstall tool with old naming scheme
    helm.delete.assert_called_with(True, old_release_name)

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


@pytest.mark.parametrize(
    "chart_version, expected_app_version",
    [
        (None, None),
        ("1.0.0", None),
        ("2.2.5", "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"),
    ],
    ids=["no-chart-installed", "old-chart-version", "new-chart-version",],
)
def test_tool_deployment_get_installed_app_version(
    helm_repository_index, cluster, chart_version, expected_app_version
):
    tool = Tool(chart_name="rstudio")
    user = User(username="test-user")
    td = ToolDeployment(tool, user)
    id_token = "dummy"

    cluster_td = cluster.ToolDeployment.return_value
    cluster_td.get_installed_chart_version.return_value = chart_version

    assert td.get_installed_app_version(id_token) == expected_app_version
    cluster.ToolDeployment.assert_called_with(user, tool)
    cluster_td.get_installed_chart_version.assert_called_with(id_token)


@pytest.mark.parametrize(
    "chart_version, expected_app_version",
    [
        ("unknown-version", None),
        ("1.0.0", None),
        ("2.2.5", "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"),
    ],
    ids=["unknown-version", "chart-with-no-appVersion", "chart-with-appVersion",],
)
def test_tool_app_version(helm_repository_index, chart_version, expected_app_version):
    tool = Tool(chart_name="rstudio", version=chart_version)

    assert tool.app_version == expected_app_version
