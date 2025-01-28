# Standard library
from unittest.mock import patch

# Third-party
from rest_framework import status
from rest_framework.reverse import reverse

# First-party/Local
from tests.api.models.test_tool import tool  # noqa: F401


def test_get(client):
    response = client.get(reverse("tool-deployments", ("rstudio", "deploy")))
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_post_not_valid_data(client):
    data = {"tool": 1000}
    response = client.post(reverse("tool-deployments", ("rstudio", "deploy")), data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_post_not_supported_action(client, tool):  # noqa: F811
    data = {"tool": tool.pk}
    response = client.post(reverse("tool-deployments", ("rstudio", "testing")), data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@patch("controlpanel.api.serializers.ToolDeploymentSerializer.save")
def test_post(save, client, tool):  # noqa: F811
    data = {"tool": tool.pk}
    response = client.post(reverse("tool-deployments", ("rstudio", "deploy")), data)
    assert response.status_code == status.HTTP_200_OK
    save.assert_called_once()
