import json
import logging

import boto3
from botocore.exceptions import ClientError
from django.conf import settings

from control_panel_api.management.commands.dry_runnable import DryRunnable
from control_panel_api.models import User


IAM = boto3.client('iam')
POLICY_NAME = f'{settings.ENV}-read-user-roles-inline-policies'
POLICY_ARN = f"{settings.IAM_ARN_BASE}:policy/{POLICY_NAME}"
POLICY_DOCUMENT = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "CanReadUserRolesInlinePolicies",
            "Effect": "Allow",
            "Action": [
                "iam:GetRolePolicy"
            ],
            "Resource": [
                f"{settings.IAM_ARN_BASE}:role/{settings.ENV}_user_*",
            ],
        },
    ],
}


logger = logging.getLogger(__name__)


def create_policy():
    try:
        IAM.create_policy(
            PolicyName=POLICY_NAME,
            PolicyDocument=json.dumps(POLICY_DOCUMENT),
        )
        logger.info(f'IAM policy "{POLICY_NAME}" created')
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            logger.warning(f'IAM policy "{POLICY_NAME}" already exists')
        else:
            raise e


def attach_policy(role_name):
    try:
        IAM.attach_role_policy(
            RoleName=role_name,
            PolicyArn=POLICY_ARN,
        )
    except ClientError as e:
        if e.response['Error']['Code'] in ('NoSuchEntity', 'ValidationError'):
            logger.warning(f'IAM role "{role_name}" not found or invalid')
        else:
            raise e


class Command(DryRunnable):
    """
    Creates the "${ENV}-read-users-inline-policies" IAM role and attaches
    it to all users' IAM roles

    NOTE: Needs permissions to `iam:CreatePolicy` and `iam:AttachRolePolicy`
    """

    help = __doc__

    def handle(self, *args, **options):
        logger.info(f'Creating IAM policy "{POLICY_NAME}"...')
        if not options['dry_run']:
            create_policy()

        for user in User.objects.all():
            role_name = user.iam_role_name
            logger.info(f'Attaching to IAM role "{role_name}"...')
            if not options['dry_run']:
                attach_policy(role_name)
