# Standard library
import subprocess
import time
from unittest.mock import MagicMock, patch

# Third-party
import pytest
from django.conf import settings

# First-party/Local
from controlpanel.api import helm

# ------ Original unit tests


def test_chart_app_version():
    app_version = "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"
    chart = helm.HelmChart(
        "rstudio",
        "RStudio with Auth0 authentication proxy",
        "2.2.5",
        app_version,
        "https://testing/rstudio.tgz",
    )

    assert chart.app_version == app_version


def test_helm_repository(helm_repository_index):
    with patch("builtins.open", helm_repository_index):
        # See tests/api/fixtures/helm_mojanalytics_index.py
        entries = helm.get_helm_entries()
        rstudio_info = entries.get("rstudio")

        rstudio_2_2_5_app_version = "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"

        assert len(rstudio_info) == 2
        assert "2.2.5" in rstudio_info[0]["version"]
        assert "1.0.0" in rstudio_info[1]["version"]

        assert rstudio_info[0].get("appVersion") == rstudio_2_2_5_app_version
        # Helm added `appVersion` field in metadata only
        # "recently" so for testing that for old chart
        # version this returns `None`
        assert rstudio_info[1].get("appVersion") is None


@pytest.mark.parametrize(
    "chart_name, version, expected_app_version",
    [
        ("notfound", "v42", None),
        ("rstudio", "unknown-version", None),
        ("rstudio", "1.0.0", None),
        (
            "rstudio",
            "2.2.5",
            "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10",
        ),
    ],
    ids=[
        "unknown-chart",
        "unknown-version",
        "chart-with-no-appVersion",
        "chart-with-appVersion",
    ],
)
def test_helm_repository_get_chart_app_version(
    helm_repository_index, chart_name, version, expected_app_version
):
    # See tests/api/fixtures/helm_mojanalytics_index.py
    with patch("builtins.open", helm_repository_index):
        app_version = helm.get_chart_app_version(chart_name, version)
        assert app_version == expected_app_version


def test_helm_upgrade_release():
    mock_execute = MagicMock()
    mock_update = MagicMock()
    with (
        patch("controlpanel.api.helm._execute", mock_execute),
        patch("controlpanel.api.helm.update_helm_repository", mock_update),
    ):
        upgrade_args = (
            "release-name",
            "helm-chart-name",
            "--namespace=user-alice",
            "--set=username=alice",
        )
        helm.upgrade_release(*upgrade_args)

        mock_update.assert_called_once_with()

        mock_execute.assert_called_with(
            "upgrade",
            "--install",
            "--force",
            "--wait",
            "--timeout",
            "7m0s",
            *upgrade_args,
        )


# ------ New (comprehensive) unit tests.


def test_execute_ignores_debug():
    """
    If the DEBUG flag is set in the environment, ensure this is removed before
    calling the helm command via Popen (apparently, helm checks for the
    existence of DEBUG env var, and we don't want this to happen).
    """
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_Popen = MagicMock(return_value=mock_proc)
    mock_environ = MagicMock()
    mock_environ.copy.return_value = {"DEBUG": "1"}
    with (
        patch("controlpanel.api.helm.subprocess.Popen", mock_Popen),
        patch("controlpanel.api.helm.os.environ", mock_environ),
    ):
        helm._execute("delete", "foo")
    mock_Popen.assert_called_once_with(
        ["helm", "delete", "foo"],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding="utf8",
        env={},  # Missing the DEBUG flag.
    )


def test_execute_with_failing_process():
    """
    Ensure a HelmError is raised if the subprocess was unable to run.
    """
    mock_process = MagicMock()
    mock_process.wait.side_effect = subprocess.SubprocessError()
    mock_process.communicate.return_value = ("boom", "bang")
    mock_Popen = MagicMock(return_value=mock_process)
    with pytest.raises(helm.HelmError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            helm._execute("delete", "foo")


def test_execute_with_oserror():
    """
    Ensure a HelmError is raised if any other sort of exception is encountered.
    """
    mock_Popen = MagicMock(side_effect=OSError("Boom"))
    with pytest.raises(helm.HelmError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            helm._execute("delete", "foo")


def test_execute_with_failing_helm_command():
    """
    Ensure a HelmError is raised if the helm command returns a non-0 code.
    """
    mock_proc = MagicMock()
    mock_proc.returncode = 1  # Boom ;-)
    mock_proc.communicate.return_value = ("boom", "bang")
    mock_Popen = MagicMock(return_value=mock_proc)
    with pytest.raises(helm.HelmError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            helm._execute("delete", "foo")
            mock_proc.communicate.assert_called_once()


@pytest.mark.parametrize("timeout", [None, 60])
def test_execute_waits(timeout):
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_Popen = MagicMock(return_value=mock_proc)

    with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
        helm._execute("foo", "bar")

    mock_proc.wait.assert_called_once()
    mock_proc.communicate.assert_not_called()
    assert mock_proc.returncode == 0


def test_update_helm_repository_non_existent_cache(helm_repository_index):
    """
    If this is a fresh instance and there's no existing helm repository cache,
    ensure the function updates the helm repository, then returns the YAML
    parsed helm repository cache.
    """
    with (
        patch("builtins.open", helm_repository_index),
        patch("controlpanel.api.helm._execute") as mock_execute,
        patch("controlpanel.api.helm.os.path.getmtime", return_value=time.time()),
        patch("controlpanel.api.helm.os.path.exists", return_value=False),
    ):
        helm.update_helm_repository()
        mock_execute.assert_called_once_with("repo", "update")


def test_update_helm_repository_valid_cache(helm_repository_index):
    """
    Ensure the function does NOT update the helm repository, because the helm
    cache is still within the valid age, then returns the YAML
    parsed helm repository cache.
    """
    with (
        patch("builtins.open", helm_repository_index),
        patch("controlpanel.api.helm._execute") as mock_execute,
        patch("controlpanel.api.helm.os.path.getmtime", return_value=time.time() - 1),
        patch("controlpanel.api.helm.os.path.exists", return_value=True),
    ):
        helm.update_helm_repository()
        assert mock_execute.call_count == 0


def test_delete():
    """
    The delete function (helm 3)results in the expected helm command to be
    executed.
    """
    with patch("controlpanel.api.helm._execute") as mock_execute:
        helm.delete("my_namespace", "foo", "bar", "baz")
        mock_execute.assert_called_once_with(
            "uninstall",
            "foo",
            "bar",
            "baz",
            "--namespace",
            "my_namespace",
            "--wait",
            "--timeout",
            settings.HELM_DELETE_TIMEOUT,
            dry_run=False,
        )


def test_list_releases_with_release():
    """
    Given a certain release, returns a list of the results.
    """
    mock_proc = MagicMock()
    mock_proc.stdout.read.return_value = "foo bar baz qux"
    mock_execute = MagicMock(return_value=mock_proc)
    with patch("controlpanel.api.helm._execute", mock_execute):
        result = helm.list_releases(release="rstudio")
        assert result == [
            "foo",
            "bar",
            "baz",
            "qux",
        ]
        mock_execute.assert_called_once_with("list", "-aq", "--filter", "rstudio")


def test_list_releases_with_namespace():
    """
    Given a certain namespace, returns a list of the results.
    """
    mock_proc = MagicMock()
    mock_proc.stdout.read.return_value = "foo bar baz qux"
    mock_execute = MagicMock(return_value=mock_proc)
    with patch("controlpanel.api.helm._execute", mock_execute):
        result = helm.list_releases(namespace="some-ns")
        assert result == [
            "foo",
            "bar",
            "baz",
            "qux",
        ]
        mock_execute.assert_called_once_with("list", "-aq", "--namespace", "some-ns")


@pytest.mark.parametrize(
    "stderr, stdout, raise_error",
    [
        ("Error: release: already exists", "All good", False),
        ("Error: Something that should throw", "All good", True),
        ("All good", "Error: Something that should throw", True),
        ("All good", "All good", False),
        (
            (
                "Error: uninstallation completed with 1 error(s): "
                "uninstall: Failed to purge the release"
            ),
            "All good",
            False,
        ),
    ],
)
def test_should_raise_error(stderr, stdout, raise_error):
    result = helm.should_raise_error(stderr, stdout)
    assert result == raise_error
