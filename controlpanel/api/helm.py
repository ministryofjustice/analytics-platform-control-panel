from datetime import datetime, timedelta
import logging
import os
import re
import subprocess

from django.conf import settings
from rest_framework.exceptions import APIException
import yaml


log = logging.getLogger(__name__)


class HelmError(APIException):
    status_code = 500
    default_code = "helm_error"
    default_detail = "Error executing Helm command"


class Helm(object):

    @classmethod
    def execute(cls, *args, check=True, **kwargs):
        should_wait = False
        if 'timeout' in kwargs:
            should_wait = True
            timeout = kwargs.pop('timeout')

        try:
            log.debug(' '.join(['helm', *args]))
            env = os.environ.copy()
            # helm checks for existence of DEBUG env var
            if 'DEBUG' in env:
                del env['DEBUG']
            proc = subprocess.Popen(
                ["helm", *args],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='utf8',
                env=env,
                **kwargs,
            )

        except ValueError as invalid_args_err:
            log.error(invalid_args_err)
            raise HelmError(invalid_args_err)

        except subprocess.CalledProcessError as execution_err:
            error_output = execution_err.stderr.read()
            log.error(error_output)
            raise HelmError(error_output)

        except OSError as file_not_found:
            log.error(str(file_not_found))
            raise HelmError(file_not_found)

        if should_wait:
            try:
                proc.wait(timeout)
            except subprocess.TimeoutExpired as timed_out:
                log.warning(timed_out)
                raise HelmError(timed_out)

        if check and proc.returncode:
            error_output = proc.stderr.read()
            log.warning(error_output)
            raise HelmError(error_output)

        return proc

    def upgrade_release(self, release, chart, *args):
        HelmRepository.update()

        return self.__class__.execute(
            "upgrade", "--install", "--wait", "--force", release, chart, *args,
        )

    def delete(self, purge=True, *args):
        default_args = []
        if purge:
            default_args.append("--purge")
        self.__class__.execute("delete", *default_args, *args)

    def list_releases(self, *args):
        # TODO - use --max and --offset to paginate through releases
        proc = self.__class__.execute("list", "-q", "--max=1024", *args, timeout=None)
        return proc.stdout.read().split()


def parse_upgrade_output(output):
    section = None
    columns = None
    last_deployed = None
    namespace = ''
    resource_type = None
    resources = {}
    notes = []

    for line in output.split('\n'):

        if line.startswith('LAST DEPLOYED:'):
            last_deployed = datetime.strptime(
                line.split(':', 1)[1],
                ' %a %b %d %H:%M:%S %Y',
            )
            continue

        if line.startswith('NAMESPACE:'):
            namespace = line.split(':', 1)[1].strip()
            continue

        if line.startswith('==> ') and section == 'RESOURCES':
            resource_type = line.split(' ', 1)[1].strip()
            continue

        if line.startswith('RESOURCES:'):
            section = 'RESOURCES'
            continue

        if line.startswith('NAME') and resource_type:
            columns = line.lower()
            columns = re.split(r'\s+', columns)
            continue

        if section == 'NOTES':
            notes.append(line)
            continue

        if line.startswith('NOTES:'):
            section = 'NOTES'
            continue

        if section and line.strip():
            row = re.split(r'\s+', line)
            row = dict(zip(columns, row))
            resources[resource_type] = [
                *resources.get(resource_type, []),
                *[row],
            ]

    return {
        'last_deployed': last_deployed,
        'namespace': namespace,
        'resources': resources,
        'notes': '\n'.join(notes),
    }


class Chart(object):

    def __init__(self, name, description, version, app_version):
        self.name = name
        self.description = description
        self.version = version
        self.app_version = app_version


class HelmRepository(object):

    CACHE_FOR_MINUTES = 30

    HELM_HOME = Helm.execute("home").stdout.read().strip()
    REPO_PATH = os.path.join(
        HELM_HOME,
        "repository",
        "cache",
        f"{settings.HELM_REPO}-index.yaml",
    )

    _updated_at = None
    _repository = {}

    @classmethod
    def update(cls, force=True):
        if force or cls._outdated():
            Helm.execute("repo", "update", timeout=None)
            cls._load()
            cls._updated_at = datetime.utcnow()

    @classmethod
    def _load(cls):
        # Read and parse helm repository YAML file
        try:
            with open(cls.REPO_PATH) as f:
                cls._repository = yaml.load(f, Loader=yaml.FullLoader)
        except Exception as err:
            wrapped_err = HelmError(err)
            wrapped_err.detail = f"Error while opening/parsing helm repository cache: '{cls.REPO_PATH}'"
            raise HelmError(wrapped_err)

    @classmethod
    def get_chart_info(cls, name):
        """
        Get information about the given chart

        Returns a dictionary with the chart versions as keys and the chart
        as value (`Chart` instance)

        Returns an empty dictionary when the chart is not in the helm
        repository index.

        ```
        rstudio_info = HelmRepository.get_chart_info("rstudio")
        # rstudio_info = {
        #   "2.2.5": <Chart name="rstudio" version="2.2.5" app_version=""RStudio: 1.2.13...">,
        #   "2.2.4": <Chart ...>,
        # }
        ```
        """

        cls.update(force=False)

        try:
            versions = cls._repository["entries"][name]
        except KeyError:
            # No such a chart with this name, returning {}
            return {}

        # Convert to dictionary
        chart_info = {}
        for version_info in versions:
            chart = Chart(
                version_info["name"],
                version_info["description"],
                version_info["version"],
                # appVersion is relatively new and some old helm chart don't
                # have it
                version_info.get("appVersion", None),
            )
            chart_info[chart.version] = chart
        return chart_info

    @classmethod
    def get_chart_app_version(cls, name, version):
        """
        Returns the "appVersion" metadata for the given
        chart name/version.

        It returns None if the chart or the chart version
        are not found or if that version of a chart doesn't
        have the "appVersion" field (e.g. the chart
        preceed the introduction of this field)
        """

        chart_info = cls.get_chart_info(name)
        version_info = chart_info.get(version, None)
        if version_info:
            return version_info.app_version

        return None

    @classmethod
    def _outdated(cls):
        # helm update never called?
        if not cls._updated_at:
            return True

        # helm update called more than `CACHE_FOR_MINUTES` ago
        now = datetime.utcnow()
        elapsed = now - cls._updated_at
        if elapsed > timedelta(minutes=cls.CACHE_FOR_MINUTES):
            return True

        # helm update called recently
        return False


helm = Helm()
