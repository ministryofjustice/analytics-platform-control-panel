# Standard library
from unittest.mock import MagicMock, patch

# Third-party
import pytest
from django.conf import settings
from django.utils import timezone
from model_bakery import baker

# First-party/Local
from controlpanel.api.models import Tool, ToolDeployment, User


@pytest.fixture
def tool(db):
    return baker.make("api.Tool", chart_name="rstudio", version="1.0.0", image_tag="0.0.1")


def test_deploy_for_generic(helm, tool, users):
    user = users["normal_user"]

    tool_deployment = ToolDeployment.objects.create(tool=tool, user=user, is_active=True)
    tool_deployment.deploy()

    # install new release
    helm.upgrade_release.assert_called_with(
        f"{tool.chart_name}-{user.slug}"[: settings.MAX_RELEASE_NAME_LEN],
        f"mojanalytics/{tool.chart_name}",
        "--version",
        tool.version,
        "--namespace",
        user.k8s_namespace,
        "--set",
        f"username={user.username}",
        "--set",
        f"Username={user.username}",
        "--set",
        f"aws.iamRole={user.iam_role_name}",
        "--set",
        f"toolsDomain={settings.TOOLS_DOMAIN}",
        "--set",
        f"rstudio.image.tag={tool.image_tag}",
    )


@pytest.fixture
def cluster():
    with patch("controlpanel.api.models.tool.cluster") as cluster:
        yield cluster


@pytest.mark.django_db
@pytest.mark.parametrize(
    "chart_version, expected_description",
    [
        ("unknown-version", ""),
        ("1.0.0", ""),
        ("2.2.5", "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"),
    ],
    ids=[
        "unknown-version",
        "chart-with-no-appVersion",
        "chart-with-appVersion",
    ],
)
def test_tool_description_from_helm_chart(
    helm_repository_index, chart_version, expected_description
):
    tool = Tool(chart_name="rstudio", version=chart_version).save()

    assert tool.description == expected_description


@pytest.mark.parametrize(
    "chart_name, expected",
    [
        ("jupyter-lab-datascience-notebook", "jupyter.tag"),
        ("jupyter-lab-all-spark", "jupyter.tag"),
        ("jupyter-lab", "jupyterlab.image.tag"),
        ("rstudio", "rstudio.image.tag"),
        ("vscode", "vscode.image.tag"),
    ],
    ids=[
        "jupyter-lab-datascience-notebook",
        "jupyter-lab-all-spark",
        "jupyter-lab",
        "rstudio",
        "vscode",
    ],
)
def test_image_tag_key(tool, chart_name, expected):
    tool.chart_name = chart_name
    assert tool.image_tag_key == expected


def test_get_deprecated_message(tool):
    assert tool.get_deprecated_message == ""
    tool.is_deprecated = True
    assert tool.get_deprecated_message == tool.DEFAULT_DEPRECATED_MESSAGE
    tool.deprecated_message = "This tool is deprecated"
    assert tool.get_deprecated_message == "This tool is deprecated"
    tool.is_retired = True
    assert tool.get_deprecated_message == ""


def test_tool_status():
    tool = Tool(is_restricted=False, is_deprecated=False, is_retired=False)
    assert tool.status == "Active"
    tool.is_restricted = True
    assert tool.status == "Restricted"
    tool.is_deprecated = True
    assert tool.status == "Deprecated"
    tool.is_retired = True
    assert tool.status == "Retired"


def test_status_colour():
    tool = Tool(is_restricted=False, is_deprecated=False, is_retired=False)
    assert tool.status_colour == "green"
    tool.is_restricted = True
    assert tool.status_colour == "yellow"
    tool.is_deprecated = True
    assert tool.status_colour == "grey"
    tool.is_retired = True
    assert tool.status_colour == "red"


@patch(
    "django.utils.timezone.now",
    return_value=timezone.datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.timezone.utc),
)
@patch("controlpanel.api.models.tool.ClockedSchedule")
@patch("controlpanel.api.models.tool.PeriodicTask")
def test_uninstall_deployments(task, clocked, mock_now):
    tool = Tool(pk=123, description="Test description", is_retired=True)
    expected_run_at = timezone.datetime(2025, 1, 2, 3, 0, 0, tzinfo=timezone.timezone.utc)
    clocked_mock = MagicMock()
    clocked.objects.get_or_create.return_value = (clocked_mock, True)

    tool.uninstall_deployments()

    mock_now.assert_called_once()
    clocked.objects.get_or_create.assert_called_once_with(
        clocked_time=expected_run_at,
    )
    task.objects.update_or_create.assert_called_once_with(
        name=f"Uninstall active deployments: {tool.description} ({tool.pk})",
        defaults={
            "clocked": clocked_mock,
            "task": "controlpanel.api.tasks.tools.uninstall_tool",
            "kwargs": f'{{"tool_pk": {tool.pk}}}',
            "expires": expected_run_at + timezone.timedelta(hours=3),
            "one_off": True,
            "enabled": True,
        },
    )


@pytest.mark.django_db
@patch("controlpanel.api.models.tool.helm")
@pytest.mark.parametrize("is_retired", [True, False])
def test_save(mock_helm, is_retired):
    tool = Tool(
        chart_name="rstudio",
        version="1.0.0",
        image_tag="0.0.1",
        description="Test description",
        is_retired=is_retired,
    )

    with patch.object(Tool, "uninstall_deployments") as uninstall_deployments:
        tool.save()

        mock_helm.update_helm_repository.assert_called_once_with(force=True)
        assert bool(uninstall_deployments.mock_calls) == is_retired
