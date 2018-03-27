import json
import logging

import boto3
from botocore.exceptions import ClientError
from django.core.management.base import BaseCommand

from control_panel_api.models import User


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    For each of the users in the DB, it collects its attached IAM policies
    and prints this data to stdout.

    NOTE: Needs permission to perform `iam:ListAttachedRolePolicies` action.
    """

    help = __doc__

    def handle(self, *args, **options):
        iam = boto3.client('iam')

        dump = {}

        for user in User.objects.all():
            username = user.username
            role_name = user.iam_role_name

            dump[username] = {
                'iam_role_name': role_name,
                'attached_policies': [],
            }

            try:
                policies = iam.list_attached_role_policies(
                    RoleName=role_name,
                    MaxItems=1000,
                )
                if policies:
                    dump[username]['attached_policies'] = policies["AttachedPolicies"]
            except ClientError as e:
                if e.response['Error']['Code'] in ('NoSuchEntity', 'ValidationError'):
                    logger.warning(
                        f'Error reading policies from IAM role "{role_name}": '
                        f'user "{user.username}" ("{user.pk}"): {e}'
                    )
                    dump[username]['error'] = str(e)
                    continue
                else:
                    raise e

        print(json.dumps(dump, indent=4))
