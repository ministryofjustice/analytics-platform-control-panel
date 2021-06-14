import logging
import os
import re
import subprocess
import yaml
import time
from datetime import datetime, timedelta
from django.conf import settings
from rest_framework.exceptions import APIException


log = logging.getLogger(__name__)


# Cache helm repository metadata for 5 minutes (expressed as seconds).
CACHE_FOR_MINUTES = 5 * 60


# TODO: Work out the story for HELM_HOME
HELM_HOME = "/tmp/helm"  # Helm.execute("home").stdout.read().strip()
REPO_PATH = os.path.join(
    HELM_HOME,
    "cache",
    "repository",
    f"{settings.HELM_REPO}-index.yaml",
)


class HelmError(APIException):
    status_code = 500
    default_code = "helm_error"
    default_detail = "Error executing Helm command"


class HelmChart:
    """
    Instances represent a Helm chart.
    """

    def __init__(self, name, description, version, app_version):
        self.name = name
        self.description = description  # Human readable description.
        self.version = version  # Helm chart version.
        self.app_version = app_version  # App version used in the chart.


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
    log.info("Helm process args: " + str(kwargs))
    # Flag to indicate if the helm process will be blocking.
    wait = False
    # The timeout value will be passed into the process's wait method. See the
    # Python docs for the blocking behaviour this causes.
    if "timeout" in kwargs:
        wait = True
        timeout = kwargs.pop("timeout")
        log.info(
            "Blocking helm command. Timout after {} seconds.".format(timeout)
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
        log.warning(stderr)
        log.warning(stdout)
        raise HelmError(stderr)
    return proc


def update_helm_repository():
    """
    Updates the helm repository and returns a dictionary representation of
    all the available charts. Raises a HelmError if there's a problem reading
    the helm repository cache.
    """
    # If there's no helm repository cache, call helm repo update to fill it.
    if not os.path.exists(REPO_PATH):
        _execute("repo", "update", timeout=None)  # timeout = infinity.
    # Execute the helm repo update command if the helm repository cache is
    # stale (older than CACHE_FOR_MINUTES value).
    if os.path.getmtime(REPO_PATH) + CACHE_FOR_MINUTES < time.time():
        _execute("repo", "update", timeout=None)  # timeout = infinity.
    try:
        with open(REPO_PATH) as f:
            return yaml.load(f, Loader=yaml.FullLoader)
    except Exception as ex:
        error = HelmError(ex)
        error.detail = (
            f"Error while opening/parsing helm repository cache: '{REPO_PATH}'"
        )
        raise HelmError(error)


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


def delete(*args):
    """
    Delete a helm chart identified by the content of the args list. Logs the
    stdout result of the command.
    """
    proc = _execute(
        "delete",
        *args,
    )
    stdout = proc.stdout.read()
    log.info(stdout)


def get_chart_info(chart_name):
    """
    Get information about the given chart.

    Returns a dictionary with the chart versions as keys and instances of the
    HelmChart class as associated values.

    Returns an empty dictionary when the chart is not in the helm repository
    index.
    """
    chart_info = {}  # The end result.
    # Update and grab repository metadata.
    repository = update_helm_repository()
    entries = repository.get("entries")
    if entries:
        versions = entries.get(chart_name)
        if versions:
            # There are versions for the referenced chart. Add them to the
            # result as HelmChart instances.
            for version in versions:
                chart = HelmChart(
                    version["name"],
                    version["description"],
                    version["version"],
                    # appVersion is relatively new so some old charts don't
                    # have it.
                    version.get("appVersion"),
                )
                chart_info[chart.version] = chart
    return chart_info


def get_chart_app_version(chart_name, chart_version):
    """
    Returns the "appVersion" metadata for the helm chart with the referenced
    name and version.

    Returns None if there's no match or if the match is missing the
    "appVersion" metadata.
    """

    chart = get_chart_info(chart_name)
    chart_at_version = chart.get(chart_version)
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
    log.info(result)
    return result.split()
