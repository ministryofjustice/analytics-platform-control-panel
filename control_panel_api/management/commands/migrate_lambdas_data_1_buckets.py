import logging
import re

import boto3
from django.conf import settings
from django.core.management.base import BaseCommand

from control_panel_api.models import S3Bucket


READWRITE = 'readwrite'


logger = logging.getLogger(__name__)


def _eligible(policy_name):
    return (policy_name.startswith(f'{settings.ENV}-') and
            not policy_name.startswith(f'{settings.ENV}-app-') and
            policy_name.endswith(READWRITE))


def _bucket_name(policy_name):
    return re.sub(f'-{READWRITE}$', '', policy_name)


class Command(BaseCommand):
    help = "Add records for S3 buckets created by AWS Lambda functions."

    def handle(self, *args, **options):
        iam_client = boto3.client('iam')

        results = iam_client.list_policies(
            Scope='Local',  # Customer managed policies only
            OnlyAttached=True,  # Ignore non-attached policies
            MaxItems=1000,
        )

        for policy in results['Policies']:
            policy_name = policy['PolicyName']

            if _eligible(policy_name):
                bucket_name = _bucket_name(policy_name)

                if not S3Bucket.objects.filter(name=bucket_name).exists():
                    S3Bucket.objects.create(
                        name=bucket_name,
                        is_data_warehouse=True,
                    )
                    logger.info(f'Created S3 bucket "{bucket_name}" record for IAM policy "{policy_name}"')
                else:
                    logger.debug(f'S3 bucket "{bucket_name}" record for IAM policy "{policy_name}" already exists')
