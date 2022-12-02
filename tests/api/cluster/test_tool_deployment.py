from unittest.mock import Mock, patch

from django.conf import settings
from controlpanel.api.cluster import ToolDeployment
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
