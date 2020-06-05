import json

import pytest
from unittest.mock import patch, Mock

from controlpanel.api.models import Tool, ToolDeployment, User
from controlpanel.api.cluster import (
    TOOL_DEPLOYING,
    TOOL_RESTARTING,
    TOOL_UPGRADED,
)
from controlpanel.frontend import consumers


@pytest.fixture
def users(db):
    print("Setting up users...")
    User(auth0_id="github|1", username="alice").save()
    User(auth0_id="github|2", username="bob").save()


@pytest.fixture
def tools(db):
    print("Setting up tools...")
    Tool(chart_name="a_tool").save()
    Tool(chart_name="another_tool").save()


@pytest.yield_fixture
def update_tool_status():
    with patch("controlpanel.frontend.consumers.update_tool_status") as update_tool_status:
        yield update_tool_status


@pytest.yield_fixture
def wait_for_deployment():
    with patch("controlpanel.frontend.consumers.wait_for_deployment") as wait_for_deployment:
        yield wait_for_deployment


def test_tool_deploy(users, tools, update_tool_status, wait_for_deployment):
    user = User.objects.first()
    tool = Tool.objects.first()
    id_token = "secret user id_token"

    with patch("controlpanel.frontend.consumers.ToolDeployment") as ToolDeployment:
        tool_deployment = Mock()
        ToolDeployment.return_value = tool_deployment

        consumer = consumers.BackgroundTaskConsumer("test")
        consumer.tool_deploy(
            message={
                "user_id": user.auth0_id,
                "tool_name": tool.chart_name,
                "id_token": id_token,
            }
        )

        # 1. Instanciate `ToolDeployment` correctly
        ToolDeployment.assert_called_with(tool, user)
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


def test_tool_upgrade(users, tools, update_tool_status):
    user = User.objects.first()
    tool = Tool.objects.first()
    id_token = "secret user id_token"

    with patch("controlpanel.frontend.consumers.ToolDeployment") as ToolDeployment:
        tool_deployment = Mock()
        ToolDeployment.return_value = tool_deployment

        message = {
            "user_id": user.auth0_id,
            "tool_name": tool.chart_name,
            "id_token": id_token,
        }

        consumer = consumers.BackgroundTaskConsumer("test")
        consumer.tool_deploy = Mock() # mock tool_deploy() method
        consumer.tool_upgrade(message=message)

        # 1. calls/reuse tool_deploy()
        consumer.tool_deploy.assert_called_with(message)
        # 2. Instanciate `ToolDeployment` correctly
        ToolDeployment.assert_called_with(tool, user)
        # 3. Send status update
        update_tool_status.assert_called_with(
            tool_deployment,
            id_token,
            TOOL_UPGRADED,
        )


def test_tool_restart(users, tools, update_tool_status, wait_for_deployment):
    user = User.objects.first()
    tool = Tool.objects.first()
    id_token = "secret user id_token"

    with patch("controlpanel.frontend.consumers.ToolDeployment") as ToolDeployment:
        tool_deployment = Mock()
        ToolDeployment.return_value = tool_deployment

        consumer = consumers.BackgroundTaskConsumer("test")
        consumer.tool_restart(
            message={
                "user_id": user.auth0_id,
                "tool_name": tool.chart_name,
                "id_token": id_token,
            }
        )

        # 1. Instanciate `ToolDeployment` correctly
        ToolDeployment.assert_called_with(tool, user)
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
    }

    consumer = consumers.BackgroundTaskConsumer("test")
    tool, user = consumer.get_tool_and_user(message)
    assert expected_user == user
    assert expected_tool == tool


def test_update_tool_status():
    tool = Tool(chart_name="a_tool", version="v1.0.0")
    user = User(auth0_id="github|123")
    id_token = "user id_token"
    status = TOOL_UPGRADED
    app_version = "R: 42, Python: 2.0.0"

    tool_deployment = Mock()
    tool_deployment.tool = tool
    tool_deployment.user = user
    tool_deployment.get_installed_app_version.return_value = app_version

    expected_sse_event = {
        "event": "toolStatus",
        "data": json.dumps({
            "toolName": tool.chart_name,
            "version": tool.version,
            "appVersion": app_version,
            "status": status,
        }),
    }

    with patch("controlpanel.frontend.consumers.send_sse") as send_sse:
        consumers.update_tool_status(
            tool_deployment,
            id_token,
            status,
        )
        tool_deployment.get_installed_app_version.assert_called_with(id_token)
        send_sse.assert_called_with(user.auth0_id, expected_sse_event)
