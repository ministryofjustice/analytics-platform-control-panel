from unittest.mock import Mock, patch

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
