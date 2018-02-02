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

    def put_bucket_tagging(self, name, tags):
        """Put bucket tagging

        :param name: Bucket name
        :param tags: Tags {key: value} e.g. {'buckettype': 'datawarehouse'}
        :type name: str
        :type tags: dict
        """
        self._do('s3', 'put_bucket_tagging',
            Bucket=name,
            Tagging={
                'TagSet': [{'Key': str(k), 'Value': str(v)} for k, v in tags.items()]
            })

    def get_inline_policy_document(self, role_name, policy_name):
        if not self.enabled:
            return None

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

    def detach_policy_from_role(self, policy_arn, role_name):
        self._do('iam', 'detach_role_policy',
            RoleName=role_name,
            PolicyArn=policy_arn)


aws = AWSClient()


class S3AccessPolicy(object):

    def __init__(self, document=None):
        self._readonly_arns = set()
        self._readwrite_arns = set()

        if document:
            self._load(document)

    def revoke_access(self, bucket_arn):
        self._readonly_arns.discard(bucket_arn)
        self._readwrite_arns.discard(bucket_arn)

    def grant_access(self, bucket_arn, readwrite=False):
        self.revoke_access(bucket_arn)

        if readwrite:
            self._readwrite_arns.add(bucket_arn)
        else:
            self._readonly_arns.add(bucket_arn)

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

        all_buckets_arns = self._readonly_arns | self._readwrite_arns
        if all_buckets_arns:
            statements.append(self._list_statement(all_buckets_arns))

        if self._readonly_arns:
            statements.append(self._readonly_statement)

        if self._readwrite_arns:
            statements.append(self._readwrite_statement)

        return {
            "Version": "2012-10-17",
            "Statement": statements,
        }

    def _list_statement(self, all_buckets_arns):
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
            "Resource": self._s3_objects_arns(self._readonly_arns),
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
            "Resource": self._s3_objects_arns(self._readwrite_arns),
        }

    def _s3_objects_arns(self, arns):
        return [f'{arn}/*' for arn in arns]

    def _s3_buckets_arns(self, arns):
        return [arn.rsplit('/*', 1)[0] for arn in arns]

    def _load(self, document):
        for statement in document['Statement']:
            sid = statement['Sid']
            if sid in ('readonly', 'readwrite'):
                arns = set(self._s3_buckets_arns(statement['Resource']))
                if sid == 'readwrite':
                    self._readwrite_arns = arns
                else:
                    self._readonly_arns = arns
