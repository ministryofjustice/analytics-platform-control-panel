import structlog
import os
import subprocess
import yaml
import time
from django.conf import settings
from rest_framework.exceptions import APIException


log = structlog.getLogger(__name__)


# Cache helm repository metadata for 5 minutes (expressed as seconds).
CACHE_FOR_MINUTES = 5 * 60


def get_repo_path():
    """
    Get the path for the repository cache.
    """
    return os.path.join(settings.HELM_REPOSITORY_CACHE, f"{settings.HELM_REPO}-index.yaml")


class HelmError(APIException):
    status_code = 500
    default_code = "helm_error"
    default_detail = "Error executing Helm command"


class HelmChart:
    """
    Instances represent a Helm chart.
    """

    def __init__(self, name, description, version, app_version, chart_url):
        self.name = name
        self.description = description  # Human readable description.
        self.version = version  # Helm chart version.
        self.app_version = app_version  # App version used in the chart.
        self.chart_url = chart_url


def _execute(*args, **kwargs):
    """
    Execute a helm command with the referenced arguments and keyword arguments.

    This function will log as much of the context as possible, and try to be
    as noisey in the logs when things go wrong.

    Returns an object representing the OS level process that's actually running
    the helm command. The caller is responsible for logging stdout in the case
    of a success or failure.
    """
    log.info(" ".join(["helm", *args]))

    if "dry_run" in kwargs and kwargs.pop("dry_run"):
        return None

    log.info("Helm process args: " + str(kwargs))
    # Flag to indicate if the helm process will be blocking.
    wait = False
    # The timeout value will be passed into the process's wait method. See the
    # Python docs for the blocking behaviour this causes.
    if "timeout" in kwargs:
        wait = True
        timeout = kwargs.pop("timeout")
        log.info(
            "Blocking helm command. Timeout after {} seconds.".format(timeout)
        )
    # Apparently, helm checks for existence of DEBUG env var, so delete it.
    env = os.environ.copy()
    if "DEBUG" in env:
        del env["DEBUG"]
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
        if "upgrade" in args or "uninstall" in args:
            # The following lines will make sure the completion of helm command
            log.info(proc.stdout.read())
            log.info(proc.stderr.read())
    except subprocess.CalledProcessError as proc_ex:
        # Subprocess specific exception handling should capture stderr too.
        log.error(proc_ex)
        log.error(proc_ex.stderr.read())
        raise HelmError(proc_ex)
    except Exception as ex:
        # Catch all other exceptions, log them and re-raise as HelmError
        # exceptions.
        log.error(ex)
        raise HelmError(ex)
    if wait:
        # Wait for blocking helm commands.
        try:
            proc.wait(timeout)
        except subprocess.TimeoutExpired as ex:
            # Raise if timed out.
            log.warning(ex)
            raise HelmError(ex)
    if proc.returncode:
        # The helm command returned a non-0 return code. Log all the things!
        stdout = proc.stdout.read()
        stderr = proc.stderr.read()
        log.warning(f"Helm Error event: returncode [{proc.returncode}], stdout [{stdout}]")
        log.warning(f"Helm Error event: returncode [{proc.returncode}], stderr [{stderr}]")
        log.warning(stderr)
        log.warning(stdout)
        raise HelmError(stderr)
    return proc


def update_helm_repository(force=False):
    """
    Updates the helm repository and returns a dictionary representation of
    all the available charts.
    """
    repo_path = get_repo_path()
    # If there's no helm repository cache, call helm repo update to fill it.
    if not os.path.exists(repo_path):
        _execute("repo", "update", timeout=None)
    else:
        # Execute the helm repo update command if the helm repository cache is
        # stale (older than CACHE_FOR_MINUTES value).
        if force or os.path.getmtime(repo_path) + CACHE_FOR_MINUTES < time.time():
            _execute("repo", "update", timeout=None)  # timeout = infinity.


def get_default_image_tag_from_helm_chart(chart_url, chart_name):
    proc = _execute("show", "values", chart_url)
    if proc:
        output = proc.stdout.read()
        values = yaml.safe_load(output) or {}
        tool_name = chart_name.split("-")[0]
        return values.get(tool_name, {}).get("tag") or \
               values.get(tool_name, {}).get("image", {}).get("tag")
    else:
        return None


def get_helm_entries():
    # Update repository metadata.
    update_helm_repository()
    # Grab repository metadata.
    repo_path = get_repo_path()
    try:
        with open(repo_path) as f:
            repository = yaml.load(f, Loader=yaml.FullLoader)
    except Exception as ex:
        error = HelmError(ex)
        error.detail = (
            f"Error while opening/parsing helm repository cache: '{repo_path}'"
        )
        raise HelmError(error)

    if not repository:
        # Metadata not available, so bail with empty dictionary.
        return {}
    return repository.get("entries")


def get_chart_version_info(entries, chart_name, chart_version):
    versions = entries.get(chart_name)
    chart = None
    # There are versions for the referenced chart. Add them to the
    # result as HelmChart instances.
    for version in versions or []:
        if version["version"] == chart_version:
            chart = HelmChart(
                version["name"],
                version["description"],
                version["version"],
                # appVersion is relatively new so some old charts don't
                # have it.
                version.get("appVersion"),
                version["urls"][0],
            )
            break
    return chart


def upgrade_release(release, chart, *args):
    """
    Upgrade to a new release version (for an app - e.g. RStudio).

    Returns the process for further processing by the caller.
    """
    update_helm_repository()
    return _execute(
        "upgrade",
        "--install",
        "--wait",
        "--force",
        release,
        chart,
        *args,
    )


def delete(namespace, *args, dry_run=False):
    """
    Delete helm charts identified by the content of the args list in the
    referenced namespace. Helm 3 version.

    This command blocks, so the old charts are deleted BEFORE the new charts
    are installed. Will block for a maximum of settings.HELM_DELETE_TIMEOUT
    seconds.

    Logs the stdout result of the command.
    """
    if not namespace:
        raise ValueError(
            "Cannot proceed: a namespace needed for removal of release."
        )
    proc = _execute(
        "uninstall",
        *args,
        "--namespace",
        namespace,
        timeout=settings.HELM_DELETE_TIMEOUT,
        dry_run=dry_run
    )
    if proc:
        stdout = proc.stdout.read()
        log.info(stdout)


def get_chart_app_version(chart_name, chart_version):
    """
    Returns the "appVersion" metadata for the helm chart with the referenced
    name and version.

    Returns None if there's no match or if the match is missing the
    "appVersion" metadata.
    """

    entries = get_helm_entries()
    chart_at_version = get_chart_version_info(entries, chart_name, chart_version)
    if chart_at_version:
        return chart_at_version.app_version
    else:
        return None


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
