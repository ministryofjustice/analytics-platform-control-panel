import json

import boto3


def create_bucket(name, region, acl='private'):
    boto3.client('s3').create_bucket(
        Bucket=name,
        ACL=acl,
        CreateBucketConfiguration={'LocationConstraint': region},
    )


def put_bucket_logging(name, target_bucket, target_prefix):
    boto3.client('s3').put_bucket_logging(
        Bucket=name,
        BucketLoggingStatus={
            'LoggingEnabled': {
                'TargetBucket': target_bucket,
                'TargetPrefix': target_prefix
            }
        }
    )


def create_policy(name, policy_document):
    boto3.client("iam").create_policy(
        PolicyName=name,
        PolicyDocument=json.dumps(policy_document)
    )


def delete_policy(policy_arn):
    boto3.client("iam").delete_policy(PolicyArn=policy_arn)


def detach_policy_from_entities(policy_arn):
    """Get all entities to which policy is attached
    See: http://boto3.readthedocs.io/en/latest/reference/services/iam.html#IAM.Client.list_entities_for_policy"""
    entities = boto3.client("iam").list_entities_for_policy(PolicyArn=policy_arn)

    for role in entities["PolicyRoles"]:
        detach_policy_from_role(policy_arn, role["RoleName"])

    for group in entities["PolicyGroups"]:
        detach_policy_from_group(policy_arn, group["GroupName"])

    for user in entities["PolicyUsers"]:
        detach_policy_from_user(policy_arn, user["UserName"])


def detach_policy_from_role(policy_arn, role_name):
    boto3.client("iam").detach_role_policy(
        RoleName=role_name,
        PolicyArn=policy_arn,
    )


def detach_policy_from_group(policy_arn, group_name):
    boto3.client("iam").detach_group_policy(
        GroupName=group_name,
        PolicyArn=policy_arn,
    )


def detach_policy_from_user(policy_arn, user_name):
    boto3.client("iam").detach_user_policy(
        UserName=user_name,
        PolicyArn=policy_arn,
    )
