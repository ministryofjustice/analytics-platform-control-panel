# Standard library
import json
from unittest.mock import Mock, patch

# Third-party
import pytest

# First-party/Local
from controlpanel.api.cluster import (
    HOME_RESETTING,
    TOOL_DEPLOYING,
    TOOL_READY,
    TOOL_RESTARTING,
)
from controlpanel.api.models import Tool, ToolDeployment, User
from controlpanel.frontend import consumers


@pytest.fixture
def users(db):
    print("Setting up users...")
    User(auth0_id="github|1", username="alice").save()
    User(auth0_id="github|2", username="bob").save()


@pytest.fixture
def tools(db):
    print("Setting up tools...")
    Tool(chart_name="a_tool", description="testing").save()
    Tool(
        chart_name="another_tool", description="testing"
    ).save()


@pytest.yield_fixture
def update_tool_status():
    with patch(
        "controlpanel.frontend.consumers.update_tool_status"
    ) as update_tool_status:
        yield update_tool_status


@pytest.yield_fixture
def update_home_status():
    with patch(
        "controlpanel.frontend.consumers.update_home_status"
    ) as update_home_status:
        yield update_home_status


@pytest.yield_fixture
def wait_for_deployment():
    with patch(
        "controlpanel.frontend.consumers.wait_for_deployment"
    ) as wait_for_deployment:
        yield wait_for_deployment


@pytest.yield_fixture
def wait_for_home_reset():
    with patch(
        "controlpanel.frontend.consumers.wait_for_home_reset"
    ) as wait_for_home_reset:
        yield wait_for_home_reset


def test_tool_deploy(users, tools, update_tool_status, wait_for_deployment):
    user = User.objects.first()
    tool = Tool.objects.first()
    id_token = "secret user id_token"

    with patch("controlpanel.frontend.consumers.ToolDeployment") as tool_deploy_fix:
        tool_deployment = Mock()
        tool_deploy_fix.return_value = tool_deployment

        consumer = consumers.BackgroundTaskConsumer()
        consumer.tool_deploy(
            message={
                "user_id": user.auth0_id,
                "tool_name": tool.chart_name,
                "id_token": id_token,
                "tool_id": tool.id,
            }
        )

        # 1. Instanciate `ToolDeployment` correctly
        tool_deploy_fix.assert_called_with(tool, user, None)
        # 2. Send status update
        update_tool_status.assert_called_with(
            tool_deployment,
            id_token,
            TOOL_DEPLOYING,
        )
        # 3. Call save() on ToolDeployment (trigger deployment)
        tool_deployment.save.assert_called()
        # 4. Wait for deployment to complete
        wait_for_deployment.assert_called_with(tool_deployment, id_token)


def test_tool_deploy_with_old_chart_name(
    users, tools, update_tool_status, wait_for_deployment
):
    user = User.objects.first()
    tool = Tool.objects.first()
    id_token = "secret user id_token"
    old_chart_name = "old-chart"

    with patch("controlpanel.frontend.consumers.ToolDeployment") as tool_deploy_mock:
        tool_deployment = Mock()
        tool_deploy_mock.return_value = tool_deployment
        # recevier = Mock()
        # sender = Mock()

        consumer = consumers.BackgroundTaskConsumer()
        consumer.tool_deploy(
            message={
                "user_id": user.auth0_id,
                "tool_name": tool.chart_name,
                "id_token": id_token,
                "old_chart_name": old_chart_name,
                "tool_id": tool.id,
            }
        )

        # 1. Instanciate `ToolDeployment` correctly
        tool_deploy_mock.assert_called_with(tool, user, old_chart_name)
        # 2. Send status update
        update_tool_status.assert_called_with(
            tool_deployment,
            id_token,
            TOOL_DEPLOYING,
        )
        # 3. Call save() on ToolDeployment (trigger deployment)
        tool_deployment.save.assert_called()
        # 4. Wait for deployment to complete
        wait_for_deployment.assert_called_with(tool_deployment, id_token)


def test_tool_restart(users, tools, update_tool_status, wait_for_deployment):
    user = User.objects.first()
    tool = Tool.objects.first()
    id_token = "secret user id_token"

    with patch("controlpanel.frontend.consumers.ToolDeployment") as tool_deploy_mock:
        tool_deployment = Mock()
        tool_deploy_mock.return_value = tool_deployment

        consumer = consumers.BackgroundTaskConsumer()
        consumer.tool_restart(
            message={
                "user_id": user.auth0_id,
                "tool_name": tool.chart_name,
                "id_token": id_token,
                "tool_id": tool.id,
            }
        )

        # 1. Instanciate `ToolDeployment` correctly
        tool_deploy_mock.assert_called_with(tool, user)
        # 2. Send status update
        update_tool_status.assert_called_with(
            tool_deployment,
            id_token,
            TOOL_RESTARTING,
        )
        # 3. Call restart() on ToolDeployment (trigger deployment)
        tool_deployment.restart.assert_called_with(id_token=id_token)
        # 4. Wait for deployment to complete
        wait_for_deployment.assert_called_with(tool_deployment, id_token)


def test_get_tool_and_user(users, tools):
    expected_user = User.objects.first()
    expected_tool = Tool.objects.first()
    message = {
        "user_id": expected_user.auth0_id,
        "tool_name": expected_tool.chart_name,
        "id_token": "not used by this method",
        "tool_id": expected_tool.id,
    }

    consumer = consumers.BackgroundTaskConsumer()
    tool, user = consumer.get_tool_and_user(message)
    assert expected_user == user
    assert expected_tool == tool


def test_get_home_reset(users, update_home_status, wait_for_home_reset):
    user = User.objects.first()

    with patch("controlpanel.frontend.consumers.HomeDirectory") as HomeDirectory:
        mock_hd = Mock()  # Mock home directory instance.
        HomeDirectory.return_value = mock_hd

        consumer = consumers.BackgroundTaskConsumer()
        consumer.home_reset(
            message={
                "user_id": user.auth0_id,
            }
        )

        # 1. Instanciate `HomeDirectory` correctly
        HomeDirectory.assert_called_with(user)
        # 2. Send status update
        update_home_status.assert_called_with(
            mock_hd,
            HOME_RESETTING,
        )
        # 3. Call restart() on ToolDeployment (trigger deployment)
        mock_hd.reset.assert_called_once_with()
        # 4. Wait for deployment to complete
        wait_for_home_reset.assert_called_with(mock_hd)


def test_update_tool_status():
    tool = Tool(chart_name="a_tool", version="v1.0.0")
    user = User(auth0_id="github|123")
    id_token = "user id_token"
    status = TOOL_READY

    tool_deployment = Mock()
    tool_deployment.tool = tool
    tool_deployment.user = user

    expected_sse_event = {
        "event": "toolStatus",
        "data": json.dumps(
            {
                "toolName": tool.chart_name,
                "version": tool.version,
                "tool_id": tool.id,
                "status": status,
            }
        ),
    }

    with patch("controlpanel.frontend.consumers.send_sse") as send_sse:
        consumers.update_tool_status(
            tool_deployment,
            id_token,
            status,
        )
        send_sse.assert_called_with(user.auth0_id, expected_sse_event)
