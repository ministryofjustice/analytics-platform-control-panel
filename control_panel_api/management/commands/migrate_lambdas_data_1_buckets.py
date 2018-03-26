import logging
import re
import os

import boto3
from django.conf import settings
from django.core.management.base import BaseCommand

from control_panel_api.models import S3Bucket

DRYRUN = os.environ.get('DRYRUN', 'false').lower() == 'true'
READWRITE = 'readwrite'


logger = logging.getLogger(__name__)


def _is_eligible(policy_name):
    return (policy_name.startswith(f'{settings.ENV}-') and
            not policy_name.startswith(f'{settings.ENV}-app-') and
            policy_name.endswith(READWRITE))


def _bucket_name(policy_name):
    return re.sub(f'-{READWRITE}$', '', policy_name)


class Command(BaseCommand):
    """
    NOTE: Needs permission to perform `iam:ListPolicies` action
    """


    help = "Add records for S3 buckets created by AWS Lambda functions."

    def handle(self, *args, **options):
        iam = boto3.client('iam')
        results = iam.list_policies(
            Scope='Local',  # Customer managed policies only
            OnlyAttached=True,  # Ignore non-attached policies
            MaxItems=1000,
        )

        for policy in results['Policies']:
            policy_name = policy['PolicyName']

            if _is_eligible(policy_name):
                bucket_name = _bucket_name(policy_name)

                s3bucket = S3Bucket.objects.filter(name=bucket_name).first()
                if not s3bucket:
                    if not DRYRUN:
                        S3Bucket.objects.create(
                            name=bucket_name,
                            is_data_warehouse=True,
                        )
                    logger.info(
                        f'Created S3 bucket "{bucket_name}" record '
                        f'for IAM policy "{policy_name}"'
                    )
                elif not s3bucket.is_data_warehouse:
                    logger.warning(
                        f'S3 bucket "{bucket_name}" record '
                        f'for IAM policy "{policy_name}" already exists and '
                        f'it is not a data warehouse bucket'
                    )
