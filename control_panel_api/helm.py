import logging
import subprocess

from django.conf import settings

from control_panel_api.utils import sanitize_dns_label


log = logging.getLogger(__name__)


class Helm(object):

    def __init__(self):
        self.enabled = settings.ENABLED['write_to_cluster']

    def _helm_command(self, command, *args):
        if self.enabled:
            try:
                subprocess.run(
                    ['helm', command] + list(args),
                    stderr=subprocess.PIPE,
                    check=True)
            except subprocess.CalledProcessError as error:
                log.error(error.stdout)
                raise error


    def _helm_shell_command(self, command_string):
        if self.enabled:
            try:
                subprocess.run(
                    f'helm {command_string}',
                    stderr=subprocess.PIPE,
                    shell=True,
                    check=True
                )
            except subprocess.CalledProcessError as error:
                log.error(error.stdout)
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
