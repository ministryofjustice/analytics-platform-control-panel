import json
import logging

import boto3
from django.conf import settings
from django.core.management.base import BaseCommand

from control_panel_api.models import User


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Adds OIDC statement to all users roles trust policies"

    def handle(self, *args, **options):
        iam = boto3.resource('iam')
        for user in User.objects.all():
            # Read role trust policy
            iam_role = iam.Role(user.iam_role_name)
            assume_role_policy_document = iam_role.assume_role_policy_document

            if not self._has_oidc_statement(assume_role_policy_document):
                # Add OIDC statement
                oidc_statement = self._oidc_statement(user.auth0_id)
                assume_role_policy_document['Statement'].append(oidc_statement)

                # Update role trust policy
                assume_role_policy = iam_role.AssumeRolePolicy()
                assume_role_policy.update(
                    PolicyDocument=json.dumps(assume_role_policy_document)
                )
                logger.info(f'OIDC statement added to "{user.iam_role_name}" trust policy.')
            else:
                logger.info(f'OIDC statement already found in "{user.iam_role_name}" trust policy. Skipping.')

    def _oidc_statement(self, oidc_sub):
        return {
            "Effect": "Allow",
            "Principal": {
                "Federated": self._oidc_provider_arn,
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    f"{settings.OIDC_DOMAIN}/:sub": oidc_sub,
                },
            },
        }

    def _has_oidc_statement(self, document):
        for statement in document['Statement']:
            try:
                oidc_provider_arn = statement['Principal']['Federated']
                if oidc_provider_arn == self._oidc_provider_arn:
                    return True
            except KeyError:
                pass

        return False

    @property
    def _oidc_provider_arn(self):
        return f"{settings.IAM_ARN_BASE}:oidc-provider/{settings.OIDC_DOMAIN}/"
