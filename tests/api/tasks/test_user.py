# Standard library
from unittest.mock import MagicMock, patch

# Third-party
import pytest

# First-party/Local
from controlpanel.api.models import User
from controlpanel.api.tasks.user import upgrade_user_helm_chart


@pytest.fixture()
def mock_get_user_model():
    with patch("controlpanel.api.tasks.user._get_model") as mock_get_model:
        mock_get_model.return_value = User
        yield mock_get_model


@patch("controlpanel.api.tasks.user.cluster.User")
def test_upgrade_user_helm_chart_user_does_not_exist(mock_cluster_user, mock_get_user_model):
    with patch.object(User.objects, "get") as mock_get:
        mock_get.side_effect = User.DoesNotExist
        upgrade_user_helm_chart("nonexistent_user", "chart_name")

    mock_get_user_model.assert_called_once_with("User")
    mock_cluster_user.assert_not_called()


@patch("controlpanel.api.tasks.user.cluster.User")
def test_upgrade_user_helm_chart_success(mock_cluster_user, mock_get_user_model):
    cluster_user_instance = MagicMock()
    mock_cluster_user.return_value = cluster_user_instance

    chart = MagicMock()
    cluster_user_instance.get_helm_chart.return_value = chart

    user_instance = MagicMock()

    with patch.object(User.objects, "get") as mock_get:
        mock_get.return_value = user_instance
        upgrade_user_helm_chart("existing_user", "chart_name")

    mock_get_user_model.assert_called_once_with("User")
    mock_cluster_user.assert_called_once_with(user_instance)
    cluster_user_instance.get_helm_chart.assert_called_once_with("chart_name")
    cluster_user_instance._run_helm_install_command.assert_called_once_with(chart)
