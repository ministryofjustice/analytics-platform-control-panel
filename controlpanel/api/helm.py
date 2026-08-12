# Standard library
import os
import subprocess

# Third-party
import structlog
from django.conf import settings
from rest_framework.exceptions import APIException

log = structlog.getLogger(__name__)


# Patterns for errors that appear during upgrades but don't prevent the deployment from succeeding.
TRANSIENT_ERROR_PATTERNS = [
    "already exists",  # resource already created
]


class HelmError(APIException):
    status_code = 500
    default_code = "helm_error"
    default_detail = "Error executing Helm command"


class HelmReleaseNotFound(HelmError):
    status_code = 404
    default_detail = "Helm release not found."
    default_code = "helm_release_not_found"


class HelmTimeoutError(HelmError):
    status_code = 504
    default_detail = "Helm operation timed out."
    default_code = "helm_timeout"


class HelmOperationInProgressError(HelmError):
    """
    Raised when another Helm operation is already in progress for the same release.
    This is a transient condition that typically resolves with a retry.
    """

    status_code = 409  # Conflict
    default_detail = "Another Helm operation is in progress. Please try again."
    default_code = "helm_operation_in_progress"


def get_chart_reference(chart_name):
    """
    Return the OCI chart reference for the referenced chart name.
    """
    return f"{settings.HELM_CHART_REPOSITORY}/{chart_name}"


def _execute(*args, **kwargs):
    """
    Execute a helm command with the referenced arguments and keyword arguments.

    This function will log as much of the context as possible, and try to be
    as noisey in the logs when things go wrong.

    Returns an object representing the OS level process that's actually running
    the helm command. The caller is responsible for logging stdout in the case
    of a success or failure.
    """

    if "dry_run" in kwargs and kwargs.pop("dry_run"):
        return None

    # Apparently, helm checks for existence of DEBUG env var, so delete it.
    env = os.environ.copy()
    if "DEBUG" in env:
        del env["DEBUG"]

    log.info(" ".join(["helm", *args]))
    log.info("Helm process kwargs: " + str(kwargs))

    # Run the helm command in a sub-process.
    try:
        proc = subprocess.Popen(
            ["helm", *args],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding="utf8",
            env=env,
            **kwargs,
        )
        # waits for process to complete or reaches helm timeout - default is 5m0s
        proc.wait()
    except OSError as ex:
        # Catch system level errors and re-raise as HelmError
        raise HelmError() from ex
    except subprocess.SubprocessError as proc_ex:
        # Catch general subprocess errors and reraise as HelmError
        proc.kill()
        outs, errs = proc.communicate()
        log.error(f"Subprocess error - stdout: {outs}, stderr: {errs}")
        raise HelmError() from proc_ex

    # check the returncode to determine if the process succeeded
    if proc.returncode == 0:
        # Even with successful return code, check for any stderr output and log as warnings
        # (e.g., transient errors during resource deletion that don't affect the overall result)
        stderr_output = proc.stderr.read()
        if stderr_output:
            log.warning(f"Helm command succeeded but with stderr output: {stderr_output}")
        log.info(f"Subprocess {id(proc)} succeeded with returncode: {proc.returncode}")
        return proc

    # something went wrong, check the outputs
    outs, errs = proc.communicate()

    # Check for specific error types
    if "error: uninstall: release not loaded" in str(errs).lower():
        raise HelmReleaseNotFound(detail=errs)

    # Check for timeout errors (context deadline exceeded)
    if "context deadline exceeded" in str(errs).lower():
        raise HelmTimeoutError(detail=errs)

    # Check for concurrent operation errors (another install/upgrade/rollback in progress)
    if "another operation" in str(errs).lower() and "in progress" in str(errs).lower():
        log.warning(f"Helm operation conflict detected: {errs}")
        raise HelmOperationInProgressError(detail=errs)

    # Check if this is a transient error that might not be fatal
    # These typically occur during resource updates due to timing/race conditions
    # IMPORTANT: We rely on subsequent status checks (wait_for_deployment) to verify actual success
    err_lower = str(errs).lower()

    # Only consider it transient if:
    # 1. It matches a known transient pattern
    # 2. It's an upgrade operation with --wait flag
    # The --wait flag ensures Helm waits for resources, and wait_for_deployment() provides
    # additional verification. Without --wait, we can't trust that resources are ready.
    is_transient_pattern = any(pattern.lower() in err_lower for pattern in TRANSIENT_ERROR_PATTERNS)
    is_upgrade_with_wait = "upgrade" in " ".join(args).lower() and "--wait" in args

    if is_transient_pattern and is_upgrade_with_wait:
        # For upgrade operations with --wait and transient errors, log as warning
        # but allow to proceed. The --wait flag ensures Helm waits for resources to be ready, and
        # wait_for_deployment() provides verification via Kubernetes API polling.
        log.warning(
            f"Helm upgrade with --wait encountered transient error (returncode: {proc.returncode}). "  # noqa
            f"Stderr: {errs}. "
            f"Stdout: {outs}. "
            "Proceeding with deployment verification via wait_for_deployment()."
        )
        # Return None instead of proc to avoid errors downstream trying to read outputs when
        # communicate() has already been called and closed the streams.
        return None

    # For all other cases, this is a real error
    log.error(
        f"Helm command failed - returncode: {proc.returncode}, stdout: {outs}, stderr: {errs}"
    )
    raise HelmError(errs)


def upgrade_release(release, chart, *args):
    """
    Upgrade to a new release version (for an app - e.g. RStudio).

    Returns the process for further processing by the caller.
    """
    return _execute(
        "upgrade",
        "--install",
        "--wait",
        "--timeout",
        "7m0s",
        release,
        chart,
        *args,
    )


def delete(namespace, *args, dry_run=False, wait=True):
    """
    Delete helm charts identified by the content of the args list in the
    referenced namespace. Helm 3 version.

    If the wait flag is set to True, this command blocks. This is the default behaviour to ensure
    that when a different tool is deployed, the old charts are deleted BEFORE the new charts are
    installed. It will block for a maximum of settings.HELM_DELETE_TIMEOUT seconds.

    Calling with wait=False is useful in cases where synchronous confirmation is not needed, such
    as when we delete a user.

    Logs the stdout result of the command.
    """
    if not namespace:
        raise ValueError("Cannot proceed: a namespace needed for removal of release.")

    wait_args = ["--wait", "--timeout", settings.HELM_DELETE_TIMEOUT] if wait else []

    proc = _execute(
        "uninstall",
        *args,
        "--namespace",
        namespace,
        *wait_args,
        dry_run=dry_run,
    )
    if proc:
        stdout = proc.stdout.read()
        log.info(stdout)


def list_releases(release=None, namespace=None):
    """
    List the releases associated with the referenced release and namespace, if
    they exist. Logs the stdout result of the command. Returns a list of the
    results.
    """
    # TODO - use --max and --offset to paginate through releases
    args = []
    if release:
        args.extend(
            [
                "--filter",
                release,
            ]
        )
    if namespace:
        args.extend(
            [
                "--namespace",
                namespace,
            ]
        )
    proc = _execute("list", "-aq", *args)
    result = proc.stdout.read()
    log.info(result.strip())
    return result.strip().split()
