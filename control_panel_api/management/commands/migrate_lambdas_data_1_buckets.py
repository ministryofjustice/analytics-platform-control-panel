import logging
import os

import boto3
from django.core.management.base import BaseCommand

from control_panel_api.management.commands.migrate_lambdas_data_utils import (
    bucket_name,
    is_eligible,
)
from control_panel_api.models import S3Bucket


DRYRUN = os.environ.get('DRYRUN', 'false').lower() == 'true'


logger = logging.getLogger(__name__)


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

            if not is_eligible(policy_name):
                continue

            s3bucket_name = bucket_name(policy_name)

            s3bucket = S3Bucket.objects.filter(name=s3bucket_name).first()
            if not s3bucket:
                if not DRYRUN:
                    S3Bucket.objects.create(
                        name=s3bucket_name,
                        is_data_warehouse=True,
                    )
                logger.info(
                    f'Created S3 bucket "{s3bucket_name}" record '
                    f'for IAM policy "{policy_name}"'
                )
            elif not s3bucket.is_data_warehouse:
                logger.warning(
                    f'S3 bucket "{s3bucket_name}" record '
                    f'for IAM policy "{policy_name}" already exists and '
                    f'it is not a data warehouse bucket'
                )
