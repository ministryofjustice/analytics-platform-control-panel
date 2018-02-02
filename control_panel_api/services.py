from contextlib import contextmanager
import logging

from botocore.exceptions import ClientError
from django.conf import settings

from control_panel_api.aws import (
    aws,
    S3AccessPolicy,
)


S3_POLICY_NAME = 's3-access'


logger = logging.getLogger(__name__)


def ignore_aws_exceptions(func):
    """Decorates a function to catch and allow exceptions that are thrown for
    existing entities or already created buckets etc, and reraise all others
    """
    exception_names = (
        'BucketAlreadyOwnedByYou',
        'EntityAlreadyExistsException',
        'NoSuchEntityException',
    )

    def inner(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except ClientError as e:
            if e.__class__.__name__ not in exception_names:
                raise e

            logger.error(f"Caught aws exception and ignored: {e}")

    return inner


@ignore_aws_exceptions
def create_role(role_name, add_saml_statement=False):
    """See: `sts:AssumeRole` required by kube2iam
    https://github.com/jtblin/kube2iam#iam-roles"""

    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            },
            {
                "Effect": "Allow",
                "Principal": {
                    "AWS":
                        f"{settings.IAM_ARN_BASE}:role/"
                        f"{settings.K8S_WORKER_ROLE_NAME}",
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    if add_saml_statement:
        saml_statement = {
            "Effect": "Allow",
            "Principal": {
                "Federated":
                    f"{settings.IAM_ARN_BASE}:saml-provider/"
                    f"{settings.SAML_PROVIDER}"
            },
            "Action": "sts:AssumeRoleWithSAML",
            "Condition": {
                "StringEquals": {
                    "SAML:aud": "https://signin.aws.amazon.com/saml"
                }
            }
        }
        role_policy['Statement'].append(saml_statement)

    aws.create_role(role_name, role_policy)


@ignore_aws_exceptions
def delete_role(role_name):
    aws.delete_role(role_name)


@ignore_aws_exceptions
def create_bucket(bucket_name, is_data_warehouse):
    aws.create_bucket(
        bucket_name,
        region=settings.BUCKET_REGION,
        acl='private')
    aws.put_bucket_logging(
        bucket_name,
        target_bucket=settings.LOGS_BUCKET_NAME,
        target_prefix=f"{bucket_name}/")
    aws.put_bucket_encryption(bucket_name)

    if is_data_warehouse:
        aws.put_bucket_tagging(
            bucket_name,
            tags={'buckettype': 'datawarehouse'}
        )


@contextmanager
def s3_access_policy(role_name):
    policy_document = aws.get_inline_policy_document(
        role_name=role_name,
        policy_name=S3_POLICY_NAME,
    )
    policy = S3AccessPolicy(document=policy_document)

    yield policy

    aws.put_role_policy(
        role_name=role_name,
        policy_name=S3_POLICY_NAME,
        policy_document=policy.document,
    )


def revoke_bucket_access(bucket_arn, role_name):
    with s3_access_policy(role_name) as policy:
        policy.revoke_access(bucket_arn)


def grant_bucket_access(bucket_arn, readwrite, role_name):
    with s3_access_policy(role_name) as policy:
        policy.grant_access(bucket_arn, readwrite=readwrite)
