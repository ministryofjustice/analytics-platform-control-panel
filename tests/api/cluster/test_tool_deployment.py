from unittest.mock import Mock, patch

from django.conf import settings
from controlpanel.api.cluster import ToolDeployment
from controlpanel.api.models import Tool, User


def test_get_installed_chart_version():
    user = User(username="test-user")
    tool = Tool(chart_name="test-chart")
    id_token = "dummy"

    installed_chart_version = "1.2.3"

    td = ToolDeployment(user, tool)

    deploy_metadata = Mock("k8s Deployment - metadata")
    deploy_metadata.labels = {
        "chart": f"{tool.chart_name}-{installed_chart_version}"
    }
    deploy = Mock("k8s Deployment", metadata=deploy_metadata)

    with patch("controlpanel.api.cluster.ToolDeployment.get_deployment") as get_deployment:
        get_deployment.return_value = deploy
        assert td.get_installed_chart_version(id_token) == installed_chart_version
        get_deployment.assert_called_with(id_token)


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
