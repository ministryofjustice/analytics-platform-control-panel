from datetime import datetime
import logging
import os
import re
import subprocess

from django.conf import settings
from rest_framework.exceptions import APIException


log = logging.getLogger(__name__)


class HelmError(APIException):
    status_code = 500
    default_code = "helm_error"
    default_detail = "Error executing Helm command"


class Helm(object):

    def _execute(self, *args, check=True, **kwargs):
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

    def update_repositories(self, *args):
        self._execute("repo", "update", timeout=None)

    def upgrade_release(self, release, chart, *args):
        self.update_repositories()

        return self._execute(
            "upgrade", "--install", "--wait", release, chart, *args,
        )

    def delete(self, purge=True, *args):
        default_args = []
        if purge:
            default_args.append("--purge")
        self._execute("delete", *default_args, *args)

    def list_releases(self, *args):
        # TODO - use --max and --offset to paginate through releases
        proc = self._execute("list", "-q", "--max=1024", *args, timeout=None)
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


helm = Helm()
