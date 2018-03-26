import re

from django.conf import settings


READWRITE = 'readwrite'


def is_eligible(policy_name):
    return (policy_name.startswith(f'{settings.ENV}-') and
            not policy_name.startswith(f'{settings.ENV}-app-') and
            policy_name.endswith(READWRITE))


def bucket_name(policy_name):
    return re.sub(f'-{READWRITE}$', '', policy_name)
