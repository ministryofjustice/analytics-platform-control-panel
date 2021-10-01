from unittest.mock import Mock, patch

from controlpanel.api.cluster import ToolDeployment
from controlpanel.api.models import Tool, User


def test_url_override_works():
    user = User(username="test-user")
    tool = Tool(chart_name="test-chart")
    id_token = "dummy"

    installed_chart_version = "1.2.3"

    td = ToolDeployment(user, tool)
    default_url = tool.url(user=user)
    assert default_url == "https://test-user-test-chart.example.com/"

    tool.url_override = "overriden"

    overriden_url = tool.url(user=user)
    assert overriden_url == "https://test-user-overriden.example.com/"