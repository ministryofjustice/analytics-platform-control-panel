import logging
import re
import os

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand

from control_panel_api.management.commands.migrate_lambdas_data_utils import (
    bucket_name,
    is_eligible,
)
from control_panel_api.models import (
    S3Bucket,
    User,
    UserS3Bucket,
)


DRYRUN = os.environ.get('DRYRUN', 'false').lower() == 'true'
READWRITE = 'readwrite'


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    NOTE: Needs permission to perform `iam:ListAttachedRolePolicies` action
    """


    help = ("Add UserS3Bucket records to reflect access to team S3 buckets "
            "granted by AWS Lambda functions.")

    def handle(self, *args, **options):
        iam = boto3.client('iam')

        for user in User.objects.all():
            role_name = user.iam_role_name

            logger.info(
                f'Migrating user "{user.username}" ("{user.auth0_id}"): '
                f'Reading policies from role "{role_name}"...'
            )
            try:
                policies = iam.list_attached_role_policies(
                    RoleName=role_name,
                    MaxItems=1000,
                )
            except ClientError as e:
                if e.response['Error']['Code'] in ('NoSuchEntity', 'ValidationError'):
                    logger.warning(
                        f'Error reading policies from IAM role "{role_name}": '
                        f'user "{user.username}" ("{user.pk}"): {e}'
                    )
                    continue
                else:
                    raise e

            if not policies:
                continue

            for policy in policies["AttachedPolicies"]:
                policy_name = policy["PolicyName"]

                if not is_eligible(policy_name):
                    continue

                s3bucket_name = bucket_name(policy_name)
                s3bucket = S3Bucket.objects.filter(name=s3bucket_name).first()
                if not s3bucket:
                    logger.critical(
                        f'S3 bucket "{s3bucket_name}" not found: '
                        f'corresponding to IAM policy "{policy_name}"'
                    )
                    continue

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
                        logger.info(
                            f'UserS3Bucket created: '
                            f'({user.username}, {s3bucket_name})'
                        )
                    except Exception as e:
                        logger.critical(
                            f'Failed to create UserS3Bucket: '
                            f'for ({user.username}, {s3bucket_name}): {e}'
                        )
                else:
                    logger.warning(
                        f'Existing UserS3Bucket ({user.username}, {s3bucket_name}) found'
                    )
