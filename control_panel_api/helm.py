import subprocess

from django.conf import settings


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
        self.upgrade_release(
            f'init-user-{username}',
            'mojanalytics/init-user',
            '--set', f'NFSHostname={settings.NFS_HOSTNAME}',
            '--set', f'Username={username}',
            '--set', f'Email={email}',
            '--set', f'Fullname={fullname}',
        )

    def config_user(self, username):
        self.upgrade_release(
            f'config-user-{username}',
            'mojanalytics/config-user',
            '--namespace', f'user-{username}',
            '--set', f'Username={username}',
        )


helm = Helm()
