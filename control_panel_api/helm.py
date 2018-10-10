import logging
import subprocess

from django.conf import settings

from control_panel_api.utils import sanitize_dns_label


log = logging.getLogger(__name__)


class Helm(object):

    def __init__(self):
        self.enabled = settings.ENABLED['write_to_cluster']

    def _helm_command(self, command, *args):
        helm_command = ['helm', command] + list(args)

        if not self.enabled:
            log.warning(f'helm commands disabled: {helm_command}')
            return

        try:
            log.warning(f'Running: {helm_command}')
            subprocess.run(
                helm_command,
                stderr=subprocess.PIPE,
                check=True)
        except subprocess.CalledProcessError as error:
            log.error(error.stderr)
            raise error


    def _helm_shell_command(self, command_string):
        helm_command = f'helm {command_string}'

        if not self.enabled:
            log.warning(f'helm shell commands disabled: {helm_command}')
            return

        try:
            log.warning(f'Running (with shell): {helm_command}')
            subprocess.run(
                helm_command,
                stderr=subprocess.PIPE,
                shell=True,
                check=True
            )
        except subprocess.CalledProcessError as error:
            log.error(error.stderr)
            raise error

    def upgrade_release(self, release, chart, *args):
        self._helm_shell_command('repo update')

        default_flags = ['--install', '--wait']
        flags = list(args) + default_flags
        self._helm_command('upgrade', release, chart, *flags)

    def init_user(self, username, email, fullname):
        username_slug = sanitize_dns_label(username)
        self.upgrade_release(
            f'init-user-{username_slug}',
            'mojanalytics/init-user',
            '--set', f'NFSHostname={settings.NFS_HOSTNAME}',
            '--set', f'Username={username_slug}',
            '--set', f'Email={email}',
            '--set', f'Fullname={fullname}',
            '--set', f'Env={settings.ENV}',
            '--set', f'OidcDomain={settings.OIDC_DOMAIN}',
        )

    def uninstall_init_user_chart(self, username):
        username_slug = sanitize_dns_label(username)
        self._helm_command('delete', f'init-user-{username_slug}', '--purge')

    def uninstall_user_charts(self, username):
        username_slug = sanitize_dns_label(username)
        self._helm_shell_command(
            f'delete --purge $(helm list -q --namespace user-{username_slug})'
        )

    def config_user(self, username):
        username_slug = sanitize_dns_label(username)
        self.upgrade_release(
            f'config-user-{username_slug}',
            'mojanalytics/config-user',
            '--namespace', f'user-{username_slug}',
            '--set', f'Username={username_slug}',
        )


helm = Helm()
