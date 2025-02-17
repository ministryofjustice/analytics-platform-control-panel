# Standard library
from unittest.mock import patch

# Third-party
import pytest
from model_bakery import baker

# First-party/Local
from controlpanel.api import helm
from controlpanel.api.models import Tool, ToolDeployment
from controlpanel.api.tasks.tools import uninstall_helm_release, uninstall_tool


@pytest.fixture
def tool():
    return baker.make(
        Tool,
        chart_name="test-chart",
        name="Test Tool",
        version="1.0.0",
        description="Test description",
        is_retired=True,
    )


@pytest.fixture
def tool_deployment(tool):
    return baker.make(
        ToolDeployment, tool=tool, tool_type=ToolDeployment.ToolType.JUPYTER, is_active=True
    )


@pytest.mark.django_db
@patch("controlpanel.api.tasks.tools.uninstall_helm_release.delay")
def test_uninstall_tool(mock_uninstall_helm_release, tool, tool_deployment):
    # Call the task with took pk
    uninstall_tool(tool.pk)

    mock_uninstall_helm_release.assert_called_once_with(
        tool_deployment.k8s_namespace, tool_deployment.release_name
    )


@pytest.mark.django_db
@patch("controlpanel.api.tasks.tools.uninstall_helm_release.delay")
def test_uninstall_tool_inactive_deployment(mock_uninstall_helm_release, tool, tool_deployment):
    # Make the deployment inactve
    tool_deployment.is_active = False
    tool_deployment.save()

    # Call the task
    uninstall_tool(tool.pk)

    mock_uninstall_helm_release.assert_not_called()


@pytest.mark.django_db
@patch("controlpanel.api.tasks.tools.uninstall_helm_release.delay")
def test_uninstall_tool_not_found(mock_uninstall_helm_release):
    # Call the task with a non-existent tool PK
    uninstall_tool(1000)

    mock_uninstall_helm_release.assert_not_called()


@patch("controlpanel.api.tasks.tools.helm.delete")
def test_uninstall_helm_release(mock_helm_delete):
    namespace = "test-namespace"
    release_name = "test-release"

    # Call the task
    uninstall_helm_release(namespace, release_name)

    # Check that the helm.delete method was called with the correct arguments
    mock_helm_delete.assert_called_once_with(namespace, release_name)


@patch("controlpanel.api.tasks.tools.helm.delete")
def test_uninstall_helm_release_not_found(mock_helm_delete):
    namespace = "test-namespace"
    release_name = "test-release"

    # Simulate HelmReleaseNotFound exception
    mock_helm_delete.side_effect = helm.HelmReleaseNotFound("Release not found")

    # Call the task
    result = uninstall_helm_release(namespace, release_name)

    mock_helm_delete.assert_called_once_with(namespace, release_name)

    assert result is None


@patch("controlpanel.api.tasks.tools.helm.delete")
def test_uninstall_helm_other_error_raises(mock_helm_delete):
    namespace = "test-namespace"
    release_name = "test-release"

    # Simulate HelmReleaseNotFound exception
    mock_helm_delete.side_effect = helm.HelmError("Some other error")

    # Call the task
    with pytest.raises(helm.HelmError):
        uninstall_helm_release(namespace, release_name)
        mock_helm_delete.assert_called_once_with(namespace, release_name)
