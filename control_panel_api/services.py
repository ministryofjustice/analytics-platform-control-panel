from django.conf import settings

from . import aws

READWRITE = 'readwrite'
READONLY = 'readonly'


def _policy_name(bucket_name, readwrite=False):
    """Prefix the policy name with bucket name, postfix with access level e.g. dev-james-readwrite"""
    return "{}-{}".format(bucket_name, READWRITE if readwrite else READONLY)


def _app_role_name(app_slug):
    return "{}_app_{}".format(settings.ENV, app_slug)


def _policy_arn(bucket_name, readwrite=False):
    """Return full bucket policy arn e.g. arn:aws:iam::1337:policy/bucketname-readonly"""
    return "{}:policy/{}".format(settings.IAM_ARN_BASE,
                                 _policy_name(bucket_name, readwrite))


def create_app_role(role_name):
    """See: `sts:AssumeRole` required by kube2iam
    https://github.com/jtblin/kube2iam#iam-roles"""
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com",
                },
                "Action": "sts:AssumeRole",
            },
            {
                "Effect": "Allow",
                "Principal": {
                    "AWS": f"{settings.IAM_ARN_BASE}:role/{settings.K8S_WORKER_ROLE_NAME}",
                },
                "Action": "sts:AssumeRole",
            }
        ]
    }

    aws.create_role(role_name, assume_role_policy)


def delete_app_role(role_name):
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
        bucket_name, region=settings.BUCKET_REGION, acl='private')
    aws.put_bucket_logging(bucket_name, target_bucket=settings.LOGS_BUCKET_NAME,
                           target_prefix="{}/".format(bucket_name))


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
    """Delete policy from attached entities first then delete policy, for both policy types"""
    policy_arn_readwrite = _policy_arn(bucket_name, readwrite=True)
    aws.detach_policy_from_entities(policy_arn_readwrite)
    aws.delete_policy(policy_arn_readwrite)

    policy_arn_readonly = _policy_arn(bucket_name, readwrite=False)
    aws.detach_policy_from_entities(policy_arn_readonly)
    aws.delete_policy(policy_arn_readonly)


def detach_bucket_access_from_app_role(app_slug, bucket_name, access_level):
    policy_arn = _policy_arn(
        bucket_name=bucket_name,
        readwrite=access_level == READWRITE
    )

    aws.detach_policy_from_role(
        policy_arn=policy_arn,
        role_name=_app_role_name(app_slug)
    )


def apps3bucket_create(apps3bucket):
    policy_arn = _policy_arn(
        apps3bucket.s3bucket.name,
        apps3bucket.has_readwrite_access(),
    )

    aws.attach_policy_to_role(
        policy_arn=policy_arn,
        role_name=_app_role_name(apps3bucket.app.slug),
    )


def apps3bucket_update(apps3bucket):
    app_role_name = _app_role_name(apps3bucket.app.slug)

    new_policy_arn = _policy_arn(
        apps3bucket.s3bucket.name,
        apps3bucket.has_readwrite_access(),
    )
    old_policy_arn = _policy_arn(
        apps3bucket.s3bucket.name,
        not apps3bucket.has_readwrite_access(),
    )

    aws.attach_policy_to_role(
        policy_arn=new_policy_arn,
        role_name=app_role_name,
    )
    aws.detach_policy_from_role(
        policy_arn=old_policy_arn,
        role_name=app_role_name,
    )

def apps3bucket_delete(apps3bucket):
    """:type apps3bucket: control_panel_api.models.AppS3Bucket"""
    detach_bucket_access_from_app_role(apps3bucket.app.slug,
                                       apps3bucket.s3bucket.name,
                                       apps3bucket.access_level)
