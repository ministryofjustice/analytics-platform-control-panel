import json

from django.conf import settings


aws_api_client = settings.AWS_API_CLIENT_HANDLER


def create_bucket(name, region, acl='private'):
    aws_api_client('s3').create_bucket(
        Bucket=name,
        ACL=acl,
        CreateBucketConfiguration={'LocationConstraint': region},
    )


def put_bucket_logging(name, target_bucket, target_prefix):
    aws_api_client('s3').put_bucket_logging(
        Bucket=name,
        BucketLoggingStatus={
            'LoggingEnabled': {
                'TargetBucket': target_bucket,
                'TargetPrefix': target_prefix
            }
        }
    )


def create_policy(name, policy_document):
    aws_api_client("iam").create_policy(
        PolicyName=name,
        PolicyDocument=json.dumps(policy_document)
    )


def delete_policy(policy_arn):
    aws_api_client("iam").delete_policy(PolicyArn=policy_arn)


def create_role(role_name, assume_role_policy):
    """Creates IAM role with the given name"""

    aws_api_client("iam").create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(assume_role_policy)
    )


def delete_role(role_name):
    """Delete the given IAM role."""

    _detach_role_policies(role_name)
    aws_api_client("iam").delete_role(RoleName=role_name)


def _detach_role_policies(role_name):
    """Detaches all the policies from the given role"""

    policies = aws_api_client("iam").list_attached_role_policies(RoleName=role_name)
    for policy in policies["AttachedPolicies"]:
        detach_policy_from_role(
            role_name=role_name,
            policy_arn=policy["PolicyArn"],
        )


def detach_policy_from_entities(policy_arn):
    """Get all entities to which policy is attached first then call separate detach operations"""
    entities = aws_api_client("iam").list_entities_for_policy(PolicyArn=policy_arn)

    for role in entities["PolicyRoles"]:
        detach_policy_from_role(policy_arn, role["RoleName"])

    for group in entities["PolicyGroups"]:
        detach_policy_from_group(policy_arn, group["GroupName"])

    for user in entities["PolicyUsers"]:
        detach_policy_from_user(policy_arn, user["UserName"])


def detach_policy_from_role(policy_arn, role_name):
    aws_api_client("iam").detach_role_policy(
        RoleName=role_name,
        PolicyArn=policy_arn,
    )


def detach_policy_from_group(policy_arn, group_name):
    aws_api_client("iam").detach_group_policy(
        GroupName=group_name,
        PolicyArn=policy_arn,
    )


def detach_policy_from_user(policy_arn, user_name):
    aws_api_client("iam").detach_user_policy(
        UserName=user_name,
        PolicyArn=policy_arn,
    )
