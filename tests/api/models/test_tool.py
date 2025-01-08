# Standard library
from unittest.mock import MagicMock, patch

# Third-party
import pytest
from django.conf import settings
from model_bakery import baker

# First-party/Local
from controlpanel.api.models import HomeDirectory, Tool, ToolDeployment, User


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


def test_home_directory_reset(cluster):
    user = User(username="test-user")
    hd = HomeDirectory(user)
    hd.reset()
    assert hd._subprocess == cluster.User(user).reset_home()


def test_home_directory_get_status():
    user = User(username="test-user")
    hd = HomeDirectory(user)
    cluster.HOME_RESETTING = "Resetting"
    hd._poll = MagicMock(return_value=cluster.HOME_RESETTING)
    hd._subprocess = True
    assert hd.get_status() == cluster.HOME_RESETTING


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
