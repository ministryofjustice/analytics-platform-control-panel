import json

import boto3
from botocore.exceptions import ClientError

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

    def get_inline_policy_document(self, role_name, policy_name):
        try:
            result = self._do('iam', 'get_role_policy',
                RoleName=role_name,
                PolicyName=policy_name,
            )
            return result['PolicyDocument']
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                pass
            else:
                raise e

    def put_role_policy(self, role_name, policy_name,  policy_document):
        self._do('iam', 'put_role_policy',
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )

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


class S3AccessPolicy(object):

    def __init__(self, document=None):
        self._readonly = set()
        self._readwrite = set()

        if document:
            self._load(document)

    def revoke_access(self, bucket_arn):
        self._readonly.discard(bucket_arn)
        self._readwrite.discard(bucket_arn)

    def grant_access(self, bucket_arn, readwrite=False):
        self.revoke_access(bucket_arn)

        if readwrite:
            self._readwrite.add(bucket_arn)
        else:
            self._readonly.add(bucket_arn)

    @property
    def document(self):
        statements = [
            {
                "Sid": "console",
                "Effect": "Allow",
                "Action": [
                    "s3:GetBucketLocation",
                    "s3:ListAllMyBuckets",
                ],
                "Resource": "arn:aws:s3:::*",
            },
        ]

        all_buckets = self._readonly | self._readwrite
        if all_buckets:
            statements.append(self._list_statement)

        if self._readonly:
            statements.append(self._readonly_statement)

        if self._readwrite:
            statements.append(self._readwrite_statement)

        return {
            "Version": "2012-10-17",
            "Statement": statements,
        }

    @property
    def _list_statement(self):
        all_buckets_arns = self._readonly | self._readwrite
        return {
            "Sid": "list",
            "Action": [
                "s3:ListBucket"
            ],
            "Effect": "Allow",
            "Resource": list(all_buckets_arns),
        }

    @property
    def _readonly_statement(self):
        return {
            "Sid": "readonly",
            "Action": [
                "s3:GetObject",
                "s3:GetObjectAcl",
                "s3:GetObjectVersion",
            ],
            "Effect": "Allow",
            "Resource": self._with_star(self._readonly),
        }

    @property
    def _readwrite_statement(self):
        return {
            "Sid": "readwrite",
            "Action": [
                "s3:GetObject",
                "s3:GetObjectAcl",
                "s3:GetObjectVersion",
                "s3:DeleteObject",
                "s3:DeleteObjectVersion",
                "s3:PutObject",
                "s3:PutObjectAcl",
                "s3:RestoreObject",
            ],
            "Effect": "Allow",
            "Resource": self._with_star(self._readwrite),
        }

    def _with_star(self, arns):
        return [f'{arn}/*' for arn in arns]

    def _without_star(self, resources):
        result = []
        for resource in resources:
            without = resource
            if resource.endswith('/*'):
                without = resource[:-2]

            result.append(without)

        return result

    def _load(self, document):
        for statement in document['Statement']:
            sid = statement['Sid']
            if sid not in ['readonly', 'readwrite']:
                continue

            arns = set(self._without_star(statement['Resource']))
            if sid == 'readwrite':
                self._readwrite = arns
            else:
                self._readonly = arns
