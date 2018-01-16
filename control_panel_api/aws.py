import json

import boto3

from django.conf import settings


class AWSClient(object):

    def __init__(self):
        self.enabled = settings.ENABLED['write_to_cluster']
        self.client = boto3.client

    def _do(self, service, method, **kwargs):
        if self.enabled:
            client = self.client(service)
            return getattr(client, method)(**kwargs)

    def create_bucket(self, name, region, acl='private'):
        self._do('s3', 'create_bucket',
            Bucket=name,
            ACL=acl,
            CreateBucketConfiguration={'LocationConstraint': region})

    def put_bucket_encryption(self, name):
        self._do('s3', 'put_bucket_encryption',
            Bucket=name,
            ServerSideEncryptionConfiguration={
                 'Rules': [
                     {
                         'ApplyServerSideEncryptionByDefault': {
                             'SSEAlgorithm': 'AES256'
                         }
                     }
                 ]
            })

    def put_bucket_logging(self, name, target_bucket, target_prefix):
        self._do('s3', 'put_bucket_logging',
            Bucket=name,
            BucketLoggingStatus={
                'LoggingEnabled': {
                    'TargetBucket': target_bucket,
                    'TargetPrefix': target_prefix
                }
            })

    def create_policy(self, name, policy_document):
        self._do('iam', 'create_policy',
            PolicyName=name,
            PolicyDocument=json.dumps(policy_document))

    def delete_policy(self, policy_arn):
        self._do('iam', 'delete_policy', PolicyArn=policy_arn)

    def create_role(self, role_name, assume_role_policy):
        """Creates IAM role with the given name"""

        self._do('iam', 'create_role',
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy))

    def delete_role(self, role_name):
        """Delete the given IAM role."""

        self._detach_role_policies(role_name)
        self._do('iam', 'delete_role', RoleName=role_name)

    def _detach_role_policies(self, role_name):
        """Detaches all the policies from the given role"""

        policies = self._do(
            'iam', 'list_attached_role_policies', RoleName=role_name)

        if policies:
            for policy in policies["AttachedPolicies"]:
                self.detach_policy_from_role(
                    role_name=role_name,
                    policy_arn=policy["PolicyArn"]
                )

    def detach_policy_from_entities(self, policy_arn):
        """
        Get all entities to which policy is attached first then call separate
        detach operations
        """
        entities = self._do(
            'iam', 'list_entities_for_policy', PolicyArn=policy_arn)

        if entities:

            for role in entities["PolicyRoles"]:
                self.detach_policy_from_role(policy_arn, role["RoleName"])

            for group in entities["PolicyGroups"]:
                self.detach_policy_from_group(policy_arn, group["GroupName"])

            for user in entities["PolicyUsers"]:
                self.detach_policy_from_user(policy_arn, user["UserName"])

    def attach_policy_to_role(self, policy_arn, role_name):
        self._do('iam', 'attach_role_policy',
            RoleName=role_name,
            PolicyArn=policy_arn)

    def detach_policy_from_role(self, policy_arn, role_name):
        self._do('iam', 'detach_role_policy',
            RoleName=role_name,
            PolicyArn=policy_arn)

    def detach_policy_from_group(self, policy_arn, group_name):
        self._do('iam', 'detach_group_policy',
            GroupName=group_name,
            PolicyArn=policy_arn)

    def detach_policy_from_user(self, policy_arn, user_name):
        self._do('iam', 'detach_user_policy',
            UserName=user_name,
            PolicyArn=policy_arn)


aws = AWSClient()
