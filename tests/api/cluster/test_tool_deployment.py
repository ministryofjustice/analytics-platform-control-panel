# Third-party
import pytest
from django.conf import settings

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import Tool, User


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
    expected = f"https://{user.slug}-rstudio.{settings.TOOLS_DOMAIN}/"
    # In the absence of a tool_domain, the chart_name (rstudio) is used.
    assert tool.url(user) == expected
    tool.chart_name = "rstudio-bespoke"
    tool.tool_domain = "rstudio"
    # Now the chart_name is custom, the tool_domain (rstudio) is used, ensuring
    # the url remains "valid".
    assert tool.url(user) == expected


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
