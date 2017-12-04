import subprocess

from django.conf import settings

from control_panel_api.utils import sanitize_dns_label


class Helm(object):

    def __init__(self):
        self.enabled = settings.ENABLED['write_to_cluster']

    def _helm_command(self, command, *args):
        if self.enabled:
            subprocess.run(['helm', command] + list(args), check=True)

    def upgrade_release(self, release, chart, *args):
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

    def config_user(self, username):
        username_slug = sanitize_dns_label(username)
        self.upgrade_release(
            f'config-user-{username_slug}',
            'mojanalytics/config-user',
            '--namespace', f'user-{username_slug}',
            '--set', f'Username={username_slug}',
        )


helm = Helm()
