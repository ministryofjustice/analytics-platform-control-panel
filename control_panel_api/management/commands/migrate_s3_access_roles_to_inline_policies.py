import logging

from botocore.exceptions import ClientError
from django.conf import settings

from control_panel_api.aws import aws, S3AccessPolicy
from control_panel_api.management.commands.dry_runnable import DryRunnable
from control_panel_api.models import (
    AppS3Bucket,
    UserS3Bucket,
)


READWRITE = 'readwrite'
READONLY = 'readonly'


logger = logging.getLogger(__name__)


def _policy_name(bucket_name, readwrite=False):
    """
    Prefix the policy name with bucket name, postfix with access level
    eg: dev-james-readwrite
    """
    return "{}-{}".format(bucket_name, READWRITE if readwrite else READONLY)


def _policy_arn(bucket_name, readwrite=False):
    """
    Return full bucket policy arn
    eg: arn:aws:iam::1337:policy/bucketname-readonly
    """
    return "{}:policy/{}".format(
        settings.IAM_ARN_BASE,
        _policy_name(bucket_name, readwrite))


class Command(DryRunnable):
    help = "Convert data access policies from managed to inline."

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]

        for klass in [UserS3Bucket, AppS3Bucket]:
            for access in klass.objects.all():
                self._update_inline_policy(access)
                self._detach_managed_policy(access)

    def _update_inline_policy(self, access):
        role_name = access.aws_role_name()
        bucket_name = access.s3bucket.name
        readwrite = access.has_readwrite_access()

        if not self.dry_run:
            access.aws_update()

        logger.info(
            f'Updated "{role_name}"\'s inline policy: '
            f'Granted access to "{bucket_name}" (readwrite={readwrite})'
        )

    def _detach_managed_policy(self, access):
        role_name = access.aws_role_name()
        bucket_name = access.s3bucket.name
        readwrite = access.has_readwrite_access()

        try:
            policy_arn = _policy_arn(
                bucket_name=bucket_name,
                readwrite=readwrite,
            )
            if not self.dry_run:
                aws.detach_policy_from_role(
                    policy_arn=policy_arn,
                    role_name=role_name,
                )

            logger.info(f'Detached managed policy "{policy_arn}" from "{role_name}"')
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                logger.warning(f'Managed policy "{policy_arn}" not attached to role "{role_name}".')
            else:
                raise e
