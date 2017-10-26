from django.conf import settings


def _get_subprocess():
    """Allow the subprocess module to be switched out at runtime for a
    magicmock to prevent real calls during testing
    """
    return settings.SUBPROCESS_MODULE


def init_user(username, email, fullname):
    helm_upgrade(
        f'init-user-{username}',
        'mojanalytics/init-user',
        '--set', f'NFSHostname={settings.NFS_HOSTNAME}',
        '--set', f'Username={username}',
        '--set', f'Email={email}',
        '--set', f'Fullname={fullname}',
    )


def config_user(username):
    helm_upgrade(
        f'config-user-{username}',
        'mojanalytics/config-user',
        '--namespace', f'user-{username}',
        '--set', f'Username={username}',
    )


def helm_upgrade(release, chart, *flags):
    default_flags = ['--install', '--wait']
    flags = list(flags) + default_flags
    _get_subprocess().run(
        ['helm', 'upgrade', release, chart] + flags, check=True)
