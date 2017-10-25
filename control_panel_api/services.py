from django.conf import settings

from . import aws

READWRITE = 'readwrite'
READONLY = 'readonly'


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
                    f"{settings.IAM_ARN_BASE}:saml_provider/"
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


def delete_role(role_name):
    aws.delete_role(role_name)


def get_policy_document(bucket_name_arn, readwrite):
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


def create_bucket(bucket_name):
    aws.create_bucket(
        bucket_name,
        region=settings.BUCKET_REGION,
        acl='private')
    aws.put_bucket_logging(
        bucket_name,
        target_bucket=settings.LOGS_BUCKET_NAME,
        target_prefix=f"{bucket_name}/")


def create_bucket_policies(bucket_name, bucket_arn):
    """Create readwrite and readonly policies for s3 bucket"""
    readwrite = True
    policy_name = _policy_name(bucket_name, readwrite)
    policy_document = get_policy_document(bucket_arn, readwrite)

    aws.create_policy(policy_name, policy_document)

    readwrite = False
    policy_name = _policy_name(bucket_name, readwrite)
    policy_document = get_policy_document(bucket_arn, readwrite)

    aws.create_policy(policy_name, policy_document)


def delete_bucket_policies(bucket_name):
    """
    Delete policy from attached entities first then delete policy, for both
    policy types
    """
    policy_arn_readwrite = _policy_arn(bucket_name, readwrite=True)
    aws.detach_policy_from_entities(policy_arn_readwrite)
    aws.delete_policy(policy_arn_readwrite)

    policy_arn_readonly = _policy_arn(bucket_name, readwrite=False)
    aws.detach_policy_from_entities(policy_arn_readonly)
    aws.delete_policy(policy_arn_readonly)


def detach_bucket_access_from_role(bucket_name, readwrite, role_name):
    policy_arn = _policy_arn(
        bucket_name=bucket_name,
        readwrite=readwrite
    )

    aws.detach_policy_from_role(
        policy_arn=policy_arn,
        role_name=role_name
    )


def attach_bucket_access_to_role(bucket_name, readwrite, role_name):
    policy_arn = _policy_arn(
        bucket_name,
        readwrite,
    )

    aws.attach_policy_to_role(
        policy_arn=policy_arn,
        role_name=role_name,
    )


def update_bucket_access(bucket_name, readwrite, role_name):
    new_policy_arn = _policy_arn(
        bucket_name,
        readwrite,
    )
    old_policy_arn = _policy_arn(
        bucket_name,
        not readwrite,
    )

    aws.attach_policy_to_role(
        policy_arn=new_policy_arn,
        role_name=role_name,
    )
    aws.detach_policy_from_role(
        policy_arn=old_policy_arn,
        role_name=role_name,
    )
