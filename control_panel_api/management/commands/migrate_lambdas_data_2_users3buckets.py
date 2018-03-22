import logging
import re
import os

import boto3
from django.conf import settings
from django.core.management.base import BaseCommand

from control_panel_api.models import (
    S3Bucket,
    User,
    UserS3Bucket,
)


DRYRUN = os.environ.get('DRYRUN', 'false').lower() == 'true'
READWRITE = 'readwrite'


logger = logging.getLogger(__name__)


def _eligible(policy_name):
    return (policy_name.startswith(f'{settings.ENV}-') and
            not policy_name.startswith(f'{settings.ENV}-app-') and
            policy_name.endswith(READWRITE))


def _bucket_name(policy_name):
    return re.sub(f'-{READWRITE}$', '', policy_name)


class Command(BaseCommand):
    """
    NOTE: Needs permission to perform `iam:ListAttachedRolePolicies` action
    """


    help = ("Add UserS3Bucket records to reflect access to team S3 buckets "
            "granted by AWS Lambda functions.")

    def handle(self, *args, **options):
        iam = boto3.client('iam')

        users = User.objects.all()
        for user in users:
            role_name = user.iam_role_name

            policies = iam.list_attached_role_policies(
                RoleName=role_name,
                MaxItems=1000,
            )

            if policies:
                for policy in policies["AttachedPolicies"]:
                    policy_name = policy["PolicyName"]
                    if _eligible(policy_name):
                        bucket_name = _bucket_name(policy_name)
                        s3bucket = S3Bucket.objects.filter(name=bucket_name)
                        if not s3bucket.exists():
                            logger.warning(f'S3 bucket "{bucket_name}" corresponding to IAM policy "{policy_name}" not found')
                            continue

                        s3bucket = s3bucket.first()

                        users3bucket = UserS3Bucket.objects.filter(
                            user=user,
                            s3bucket=s3bucket,
                        )
                        if not users3bucket.exists():
                            try:
                                if not DRYRUN:
                                    UserS3Bucket.objects.create(
                                        user=user,
                                        s3bucket=s3bucket,
                                        access_level=READWRITE,
                                    )
                                logger.info(f'UserS3Bucket created for ({user.username}, {bucket_name})')
                            except Exception as e:
                                logger.error(f'Failed to create UserS3Bucket for ({user.username}, {bucket_name}): {e}')
                        else:
                            logger.warning(f'Already found UserS3Bucket for ({user.username}, {bucket_name})')
