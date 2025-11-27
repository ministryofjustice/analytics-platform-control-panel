# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.conf import settings

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.helm import HelmError, HelmReleaseNotFound, HelmTimeoutError
from controlpanel.api.models import Tool, ToolDeployment, User


def test_url():
    """
    Ensures the URL for the tool release is properly constructed either from
    the chart_name or, if present, the tool_domain.
    """
    user = User(username="test-user")
    tool = Tool(
        name="RStudio",
        chart_name="rstudio",
        version="1.0.0",
    )
    tool_deployment = ToolDeployment(user=user, tool=tool)
    expected = f"https://{user.slug}-rstudio.{settings.TOOLS_DOMAIN}/"
    # In the absence of a tool_domain, the chart_name (rstudio) is used.
    assert tool_deployment.url == expected
    tool_deployment.chart_name = "rstudio-bespoke"
    tool_deployment.tool_domain = "rstudio"
    # Now the chart_name is custom, the tool_domain (rstudio) is used, ensuring
    # the url remains "valid".
    assert tool_deployment.url == expected


@pytest.mark.parametrize(
    "chart_name",
    [
        Tool.RSTUDIO_CHART_NAME,
        Tool.VSCODE_CHART_NAME,
        Tool.JUPYTER_ALL_SPARK_CHART_NAME,
        Tool.JUPYTER_DATASCIENCE_CHART_NAME,
        Tool.JUPYTER_LAB_CHART_NAME,
    ],
)
def test_image_tag_in_set_values(chart_name):
    """
    Test to check the image tag set on the tool instance is used in the helm values, not what is
    passed in the values dictionary.
    """
    tool = Tool(
        name="Test Tool",
        chart_name=chart_name,
        version="1.0.0",
        image_tag="0.2",
        values={"rstudio.image.tag": "0.1"},
    )
    user = User(username="test-user")
    tool_deployment = cluster.ToolDeployment(tool=tool, user=user)
    assert f"{tool.image_tag_key}=0.2" in tool_deployment._set_values()
    assert f"{tool.image_tag_key}=0.1" not in tool_deployment._set_values()


@pytest.mark.parametrize(
    "chart, expected",
    [
        (f"{Tool.RSTUDIO_CHART_NAME}-1.0.0", (Tool.RSTUDIO_CHART_NAME, "1.0.0")),
        (f"{Tool.RSTUDIO_CHART_NAME}-1.0.0-rc1", (Tool.RSTUDIO_CHART_NAME, "1.0.0-rc1")),
        (
            f"{Tool.JUPYTER_DATASCIENCE_CHART_NAME}-1.0.0",
            (Tool.JUPYTER_DATASCIENCE_CHART_NAME, "1.0.0"),
        ),
        (
            f"{Tool.JUPYTER_DATASCIENCE_CHART_NAME}-1.0.0-rc1",
            (Tool.JUPYTER_DATASCIENCE_CHART_NAME, "1.0.0-rc1"),
        ),
        (f"{Tool.JUPYTER_LAB_CHART_NAME}-1.0.0", (Tool.JUPYTER_LAB_CHART_NAME, "1.0.0")),
        (f"{Tool.JUPYTER_LAB_CHART_NAME}-1.0.0-rc1", (Tool.JUPYTER_LAB_CHART_NAME, "1.0.0-rc1")),
        (
            f"{Tool.JUPYTER_ALL_SPARK_CHART_NAME}-1.0.0",
            (Tool.JUPYTER_ALL_SPARK_CHART_NAME, "1.0.0"),
        ),
        (
            f"{Tool.JUPYTER_ALL_SPARK_CHART_NAME}-1.0.0-rc1",
            (Tool.JUPYTER_ALL_SPARK_CHART_NAME, "1.0.0-rc1"),
        ),
        (f"{Tool.VSCODE_CHART_NAME}-1.0.0", (Tool.VSCODE_CHART_NAME, "1.0.0")),
        (f"{Tool.VSCODE_CHART_NAME}-1.0.0-rc1", (Tool.VSCODE_CHART_NAME, "1.0.0-rc1")),
    ],
)
def test_get_chart_details(chart, expected):
    """
    Ensures the chart details are correctly extracted from the chart name.
    """
    assert cluster.ToolDeployment.get_chart_details(chart) == expected


def test_uninstall_success(helm):
    user = User(username="test-user")
    tool = Tool()
    cluster_tool_deployment = cluster.ToolDeployment(user=user, tool=tool)
    result = cluster_tool_deployment.uninstall()

    helm.delete.assert_called_once_with(
        cluster_tool_deployment.k8s_namespace, cluster_tool_deployment.release_name
    )
    assert result == helm.delete.return_value


@pytest.mark.parametrize(
    "error, error_raised",
    [
        (HelmReleaseNotFound, HelmReleaseNotFound),
        (HelmError, cluster.ToolDeploymentError),
    ],
)
def test_uninstall_exceptions(helm, error, error_raised):
    helm.delete.side_effect = error

    user = User(username="test-user")
    tool = Tool()
    cluster_tool_deployment = cluster.ToolDeployment(user=user, tool=tool)

    with pytest.raises(error_raised):
        cluster_tool_deployment.uninstall()
        helm.delete.assert_called_once_with(
            cluster_tool_deployment.k8s_namespace, cluster_tool_deployment.release_name
        )


@pytest.mark.parametrize(
    "error, error_raised",
    [
        (HelmTimeoutError, cluster.ToolDeploymentTimeoutError),
        (HelmError, cluster.ToolDeploymentError),
    ],
)
def test_install_exceptions(helm, error, error_raised):
    """
    Test that HelmTimeoutError is converted to ToolDeploymentTimeoutError
    and HelmError is converted to ToolDeploymentError.
    """
    helm.upgrade_release.side_effect = error

    user = User(username="test-user")
    tool = Tool(
        name="RStudio",
        chart_name=Tool.RSTUDIO_CHART_NAME,
        version="1.0.0",
        image_tag="0.2",
    )
    cluster_tool_deployment = cluster.ToolDeployment(user=user, tool=tool)

    with pytest.raises(error_raised):
        cluster_tool_deployment.install()
