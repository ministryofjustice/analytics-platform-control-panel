# Standard library
import subprocess
from unittest.mock import MagicMock, patch

# Third-party
import pytest
from django.conf import settings

# First-party/Local
from controlpanel.api import helm


def test_get_chart_reference():
    assert helm.get_chart_reference("rstudio") == f"{settings.HELM_CHART_REPOSITORY}/rstudio"


def test_helm_upgrade_release():
    mock_execute = MagicMock()
    with patch("controlpanel.api.helm._execute", mock_execute):
        upgrade_args = (
            "release-name",
            "helm-chart-name",
            "--namespace=user-alice",
            "--set=username=alice",
        )
        helm.upgrade_release(*upgrade_args)

        mock_execute.assert_called_with(
            "upgrade",
            "--install",
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


def test_execute_with_timeout_error():
    """
    Ensure a HelmTimeoutError is raised when the helm command times out
    (context deadline exceeded).
    """
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (
        "",
        "Error: context deadline exceeded",
    )
    mock_Popen = MagicMock(return_value=mock_proc)

    with pytest.raises(helm.HelmTimeoutError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            helm._execute("upgrade", "--install", "--wait", "my-release", "my-chart")


def test_execute_with_operation_in_progress_error():
    """
    Ensure HelmOperationInProgressError is raised when another Helm operation
    is already running for the same release.
    """
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (
        "",
        "Error: UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress",
    )
    mock_Popen = MagicMock(return_value=mock_proc)

    with pytest.raises(helm.HelmOperationInProgressError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            helm._execute("upgrade", "--install", "my-release", "my-chart")


def test_execute_with_not_found_during_upgrade_is_treated_as_transient():
    """
    K8s resource not-found errors (e.g. services "foo" not found) during upgrade --wait
    are treated as transient. OCI chart not-found errors end with ": not found" (colon)
    and are not matched by this pattern, so they surface as HelmError.
    """
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (
        "",
        'Error: services "vscode-user-scheduler" not found',
    )
    mock_Popen = MagicMock(return_value=mock_proc)

    with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
        result = helm._execute("upgrade", "--install", "--wait", "my-release", "my-chart")
        assert result is None


def test_execute_with_transient_error_not_during_upgrade():
    """
    Ensure transient errors are only treated as non-fatal during upgrade operations.
    For other operations (like delete), they should still raise errors.
    """
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = ("", 'Error: services "foo" not found')
    mock_Popen = MagicMock(return_value=mock_proc)

    with pytest.raises(helm.HelmError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            helm._execute("delete", "my-release")


def test_execute_with_transient_error_but_no_wait_flag():
    """
    Ensure that transient errors during upgrade WITHOUT --wait still raise an error.
    The --wait flag is required because it ensures Helm waits for resources to be ready.
    Without it, we can't trust the deployment will succeed.
    """
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (
        "",
        'Error: services "foo" not found',  # Transient error pattern
    )
    mock_Popen = MagicMock(return_value=mock_proc)

    with pytest.raises(helm.HelmError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            # No --wait flag, so should still fail
            helm._execute("upgrade", "--install", "my-release", "my-chart")


def test_execute_chart_not_found_is_not_treated_as_transient():
    """
    Ensure that a helm chart resolution failure (e.g. chart not in OCI registry)
    raises HelmError and is not silently swallowed as a transient error.
    """
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (
        "Release does not exist. Installing it now.",
        'Error: chart "vscode" matching 3.3.1 not found in mojanalytics index.',
    )
    mock_Popen = MagicMock(return_value=mock_proc)

    with pytest.raises(helm.HelmError):
        with patch("controlpanel.api.helm.subprocess.Popen", mock_Popen):
            helm._execute("upgrade", "--install", "--wait", "my-release", "my-chart")


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


def test_delete_without_wait():
    """
    The delete function with wait=False does not include --wait or --timeout flags.
    """
    with patch("controlpanel.api.helm._execute") as mock_execute:
        helm.delete("my_namespace", "foo", "bar", "baz", wait=False)
        mock_execute.assert_called_once_with(
            "uninstall",
            "foo",
            "bar",
            "baz",
            "--namespace",
            "my_namespace",
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
