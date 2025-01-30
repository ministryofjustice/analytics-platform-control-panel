# Standard library
import json
from unittest.mock import Mock, call, patch

# Third-party
import pytest

# First-party/Local
from controlpanel.api.cluster import HOME_RESETTING, TOOL_DEPLOYING, TOOL_READY, TOOL_RESTARTING
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
    Tool(chart_name="another_tool", description="testing").save()


@pytest.fixture
def update_tool_status():
    with patch("controlpanel.frontend.consumers.update_tool_status") as update_tool_status:
        yield update_tool_status


@pytest.fixture
def update_home_status():
    with patch("controlpanel.frontend.consumers.update_home_status") as update_home_status:
        yield update_home_status


@pytest.fixture
def wait_for_deployment():
    with patch("controlpanel.frontend.consumers.wait_for_deployment") as wait_for_deployment:
        yield wait_for_deployment


@pytest.fixture
def wait_for_home_reset():
    with patch("controlpanel.frontend.consumers.wait_for_home_reset") as wait_for_home_reset:
        yield wait_for_home_reset


def test_tool_deploy(users, tools, update_tool_status, wait_for_deployment):
    user = User.objects.first()
    tool = Tool.objects.first()
    tool_deployment = ToolDeployment.objects.create(tool=tool, user=user, is_active=False)
    wait_for_deployment.return_value = TOOL_READY

    with patch.object(ToolDeployment, "deploy") as deploy:
        consumer = consumers.BackgroundTaskConsumer()
        consumer.tool_deploy(
            message={
                "new_deployment_id": tool_deployment.id,
                "previous_deployment_id": None,
                "id_token": "secret user id_token",
            }
        )
        tool_deployment.refresh_from_db()

        assert tool_deployment.is_active is True
        deploy.assert_called_once()
        update_tool_status.assert_has_calls(
            calls=[
                call(tool_deployment=tool_deployment, status=TOOL_DEPLOYING),
                call(tool_deployment=tool_deployment, status=TOOL_READY),
            ]
        )
        wait_for_deployment.assert_called_with(tool_deployment, "secret user id_token")


def test_tool_deploy_with_previous_deployment(
    users, tools, update_tool_status, wait_for_deployment
):
    user = User.objects.first()
    tool = Tool.objects.first()
    previous_deployment = ToolDeployment.objects.create(tool=tool, user=user, is_active=False)
    new_deployment = ToolDeployment.objects.create(tool=tool, user=user, is_active=False)
    wait_for_deployment.return_value = TOOL_READY

    with (
        patch.object(ToolDeployment, "deploy") as deploy,
        patch.object(ToolDeployment, "uninstall") as uninstall,
    ):
        consumer = consumers.BackgroundTaskConsumer()
        consumer.tool_deploy(
            message={
                "new_deployment_id": new_deployment.id,
                "previous_deployment_id": previous_deployment.id,
                "id_token": "secret user id_token",
            }
        )
        previous_deployment.refresh_from_db()
        new_deployment.refresh_from_db()

        uninstall.assert_called_once()
        deploy.assert_called_once()
        assert previous_deployment.is_active is False
        assert new_deployment.is_active is True
        update_tool_status.assert_has_calls(
            calls=[
                call(tool_deployment=new_deployment, status=TOOL_DEPLOYING),
                call(tool_deployment=new_deployment, status=TOOL_READY),
            ]
        )
        wait_for_deployment.assert_called_with(new_deployment, "secret user id_token")


def test_tool_restart(users, tools, update_tool_status, wait_for_deployment):
    user = User.objects.first()
    tool = Tool.objects.first()
    tool_deployment = ToolDeployment.objects.create(tool=tool, user=user, is_active=True)
    id_token = "secret user id_token"

    with patch.object(ToolDeployment, "restart") as restart_mock:
        consumer = consumers.BackgroundTaskConsumer()
        consumer.tool_restart(
            message={
                "tool_deployment_id": tool_deployment.id,
                "user_id": user.auth0_id,
                "id_token": id_token,
            }
        )

        update_tool_status.assert_called_with(
            tool_deployment,
            TOOL_RESTARTING,
        )
        restart_mock.assert_called_with(id_token=id_token)

        wait_for_deployment.assert_called_with(tool_deployment, id_token)


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
            status,
        )
        send_sse.assert_called_with(user.auth0_id, expected_sse_event)
