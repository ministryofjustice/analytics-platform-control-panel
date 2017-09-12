import re

from django.conf import settings
from django.template.defaultfilters import slugify

from . import aws

READ_WRITE = 'readwrite'
READ_ONLY = 'readonly'


def _bucket_name(name):
    """Prefix the bucket name with environment e.g. dev-james"""
    return "{}-{}".format(settings.ENV, name)


def _policy_name(bucket_name, readwrite=False):
    """Prefix the policy name with bucket name, postfix with access level e.g. dev-james-readwrite"""
    return "{}-{}".format(bucket_name, READ_WRITE if readwrite else READ_ONLY)


def _policy_arn(bucket_name, readwrite=False):
    """Return full bucket policy arn e.g. arn:aws:iam::1337:policy/bucketname-readonly"""
    return "{}:policy/{}".format(settings.IAM_ARN_BASE, _policy_name(bucket_name, readwrite))


def bucket_arn(bucket_name):
    """Return bucket arn e.g. arn:aws:s3:::bucketname"""
    return "arn:aws:s3:::{}".format(bucket_name)


def app_slug(name):
    return re.sub(r'_+', '-', slugify(name))


def get_policy_document(bucket_name, readwrite):
    """Return a standard policy document for a bucket, use a boolean flag `readwrite` to add write access"""
    bucket_name_arn = bucket_arn(bucket_name)

    statements = [
        {
            "Sid": "ListBucketsInConsole",
            "Effect": "Allow",
            "Action": [
                "s3:GetBucketLocation",
                "s3:ListAllMyBuckets"
            ],
            "Resource": "arn:aws:s3:::*"
        },
        {
            "Sid": "ListObjects",
            "Action": [
                "s3:ListBucket"
            ],
            "Effect": "Allow",
            "Resource": [bucket_name_arn],
        },
        {
            "Sid": "ReadObjects",
            "Action": [
                "s3:GetObject",
                "s3:GetObjectAcl",
                "s3:GetObjectVersion",
            ],
            "Effect": "Allow",
            "Resource": "{}/*".format(bucket_name_arn)
        },
    ]

    if readwrite:
        statements.append(
            {
                "Sid": "UpdateRenameAndDeleteObjects",
                "Action": [
                    "s3:DeleteObject",
                    "s3:DeleteObjectVersion",
                    "s3:PutObject",
                    "s3:PutObjectAcl",
                    "s3:RestoreObject",
                ],
                "Effect": "Allow",
                "Resource": "{}/*".format(bucket_name_arn)
            }
        )

    return {
        "Version": "2012-10-17",
        "Statement": statements,
    }


def create_bucket(name):
    """Create an s3 bucket and add logging"""
    bucket_name = _bucket_name(name)
    aws.create_bucket(bucket_name, region=settings.BUCKET_REGION, acl='private')
    aws.put_bucket_logging(bucket_name, target_bucket=settings.LOGS_BUCKET_NAME,
                           target_prefix="{}/".format(bucket_name))


def delete_bucket(name):
    """Delete s3 bucket"""
    aws.delete_bucket(_bucket_name(name))


def create_bucket_policies(name):
    """Create readwrite and readonly policies for s3 bucket"""
    bucket_name = _bucket_name(name)
    aws.create_policy(_policy_name(bucket_name, readwrite=True), get_policy_document(bucket_name, True))
    aws.create_policy(_policy_name(bucket_name, readwrite=False), get_policy_document(bucket_name, False))


def delete_bucket_policies(name):
    """Delete policy from attached entities first then delete policy, for both policy types"""
    bucket_name = _bucket_name(name)

    policy_arn_readwrite = _policy_arn(bucket_name, readwrite=True)
    aws.detach_policy_from_entities(policy_arn_readwrite)
    aws.delete_policy(policy_arn_readwrite)

    policy_arn_readonly = _policy_arn(bucket_name, readwrite=False)
    aws.detach_policy_from_entities(policy_arn_readonly)
    aws.delete_policy(policy_arn_readonly)
