import os
import time
import pytest
import subprocess

from unittest.mock import MagicMock, patch
from controlpanel.api import helm
from django.conf import settings


# ------ Original unit tests


def test_chart_app_version():
    app_version = "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"
    chart = helm.HelmChart(
        "rstudio",
        "RStudio with Auth0 authentication proxy",
        "2.2.5",
        app_version,
    )

    assert chart.app_version == app_version


def test_helm_repository_chart_info_when_chart_not_found(
    helm_repository_index,
):
    with patch("builtins.open", helm_repository_index):
        info = helm.get_chart_info("notfound")
        assert info == {}


def test_helm_repository_chart_info_when_chart_found(helm_repository_index):
    with patch("builtins.open", helm_repository_index):
        # See tests/api/fixtures/helm_mojanalytics_index.py
        rstudio_info = helm.get_chart_info("rstudio")

        rstudio_2_2_5_app_version = (
            "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"
        )

        assert len(rstudio_info) == 2
        assert "2.2.5" in rstudio_info
        assert "1.0.0" in rstudio_info

        assert rstudio_info["2.2.5"].app_version == rstudio_2_2_5_app_version
        # Helm added `appVersion` field in metadata only
        # "recently" so for testing that for old chart
        # version this returns `None`
        assert rstudio_info["1.0.0"].app_version == None


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
    with patch("controlpanel.api.helm._execute", mock_execute), patch(
        "controlpanel.api.helm.update_helm_repository", mock_update
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
            "--wait",
            "--force",
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
    with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen), patch(
        "controlpanel.api.helm.os.environ", mock_environ
    ):
        helm._execute("delete", "foo")
    mock_Popen.assert_called_once_with(
        ["helm", "delete", "foo"],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding="utf8",
        env={},  # Missing the DEBUG flag.
    )


def test_execute_with_timeout():
    """
    Ensure the subprocess is waited on (blocks) for timeout seconds.
    """
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_Popen = MagicMock(return_value=mock_proc)
    timeout = 1
    with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
        result = helm._execute("delete", "foo", timeout=timeout)
    assert result == mock_proc
    mock_proc.wait.assert_called_once_with(timeout)


def test_execute_with_failing_process():
    """
    Ensure a HelmError is raised if the subprocess was unable to run.
    """
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = "boom"
    mock_Popen = MagicMock(
        side_effect=subprocess.CalledProcessError(
            1, "boom", stderr=mock_stderr
        )
    )
    with pytest.raises(helm.HelmError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            result = helm._execute("delete", "foo")


def test_execute_with_unforeseen_exception():
    """
    Ensure a HelmError is raised if any other sort of exception is encountered.
    """
    mock_Popen = MagicMock(side_effect=ValueError("Boom"))
    with pytest.raises(helm.HelmError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            result = helm._execute("delete", "foo")


def test_execute_with_failing_helm_command():
    """
    Ensure a HelmError is raised if the helm command returns a non-0 code.
    """
    mock_proc = MagicMock()
    mock_proc.returncode = 1  # Boom ;-)
    mock_Popen = MagicMock(return_value=mock_proc)
    with pytest.raises(helm.HelmError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            result = helm._execute("delete", "foo")


def test_update_helm_repository_non_existent_cache(helm_repository_index):
    """
    If this is a fresh instance and there's no existing helm repository cache,
    ensure the function updates the helm repository, then returns the YAML
    parsed helm repository cache.
    """
    with patch("builtins.open", helm_repository_index), patch(
        "controlpanel.api.helm._execute"
    ) as mock_execute, patch(
        "controlpanel.api.helm.os.path.getmtime", return_value=time.time()
    ), patch(
        "controlpanel.api.helm.os.path.exists", return_value=False
    ):
        helm.update_helm_repository()
        mock_execute.assert_called_once_with("repo", "update", timeout=None)


def test_update_helm_repository_valid_cache(helm_repository_index):
    """
    Ensure the function does NOT update the helm repository, because the helm
    cache is still within the valid age, then returns the YAML
    parsed helm repository cache.
    """
    with patch("builtins.open", helm_repository_index), patch(
        "controlpanel.api.helm._execute"
    ) as mock_execute, patch(
        "controlpanel.api.helm.os.path.getmtime", return_value=time.time() - 1
    ), patch(
        "controlpanel.api.helm.os.path.exists", return_value=True
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
            timeout=settings.HELM_DELETE_TIMEOUT,
            dry_run=False
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
        mock_execute.assert_called_once_with(
            "list", "-aq", "--filter", "rstudio"
        )


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
        mock_execute.assert_called_once_with(
            "list", "-aq", "--namespace", "some-ns"
        )
