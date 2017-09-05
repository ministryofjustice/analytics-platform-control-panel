import json

import boto3


def create_bucket(name, **kwargs):
    boto3.client('s3').create_bucket(
        Bucket=name,
        ACL=kwargs.get('acl', ''),
        CreateBucketConfiguration={'LocationConstraint': kwargs.get('region', '')},
    )


def put_bucket_logging(name, **kwargs):
    boto3.client('s3').put_bucket_logging(
        Bucket=name,
        BucketLoggingStatus={
            'LoggingEnabled': {
                'TargetBucket': kwargs.get('target_bucket', ''),
                'TargetPrefix': kwargs.get('target_prefix', '')
            }
        }
    )


def create_policy(name, readwrite=False):
    boto3.client("iam").create_policy(
        PolicyName=name,
        PolicyDocument=json.dumps(get_policy_document(name, readwrite)),
    )


def get_policy_document(bucket_name, readwrite):
    bucket_arn = "arn:aws:s3:::{}".format(bucket_name)

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
            "Resource": [bucket_arn],
        },
        {
            "Sid": "ReadObjects",
            "Action": [
                "s3:GetObject",
                "s3:GetObjectAcl",
                "s3:GetObjectVersion",
            ],
            "Effect": "Allow",
            "Resource": "{}/*".format(bucket_arn)
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
                "Resource": "{}/*".format(bucket_arn)
            }
        )

    return {
        "Version": "2012-10-17",
        "Statement": statements,
    }
