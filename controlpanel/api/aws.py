from copy import deepcopy
import json
import logging

import boto3
import botocore
from django.conf import settings


log = logging.getLogger(__name__)


def arn(service, resource, region="", account=""):
    service = service.lower()
    region = region.lower()
    regionless = ["iam", "s3"]
    if service in regionless:
        region = ""

    return f"arn:aws:{service}:{region}:{account}:{resource}"


def s3_arn(resource):
    return arn("s3", resource)


def iam_arn(resource, account=settings.AWS_DATA_ACCOUNT_ID):
    return arn("iam", resource, account=account)


def iam_assume_role_principal():
    '''
    returns the princical required to assume the IAM role

    - ARN of the assuming role when both roles are in same account
    - AWS account ID where the assuming IAM role is if in a different account

    See AWS example: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_policy-examples.html#example-delegate-xaccount-S3
    '''

    cross_account = settings.AWS_COMPUTE_ACCOUNT_ID != settings.AWS_DATA_ACCOUNT_ID

    if cross_account:
        return settings.AWS_COMPUTE_ACCOUNT_ID

    return iam_arn(
        f"role/{settings.K8S_WORKER_ROLE_NAME}",
        account=settings.AWS_COMPUTE_ACCOUNT_ID,
    )


BASE_ASSUME_ROLE_POLICY = {
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
                "AWS": iam_assume_role_principal(),
            },
            "Action": "sts:AssumeRole",
        },
    ],
}

OIDC_STATEMENT = {
    "Effect": "Allow",
    "Principal": {
        "Federated": iam_arn(f"oidc-provider/{settings.OIDC_DOMAIN}/"),
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
}

SAML_STATEMENT = {
    "Effect": "Allow",
    "Principal": {
        "Federated": iam_arn(f"saml-provider/{settings.SAML_PROVIDER}"),
    },
    "Action": "sts:AssumeRoleWithSAML",
    "Condition": {
        "StringEquals": {
            "SAML:aud": "https://signin.aws.amazon.com/saml",
        },
    },
}

READ_INLINE_POLICIES = f'{settings.ENV}-read-user-roles-inline-policies'

BASE_S3_ACCESS_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "console",
            "Action": [
                "s3:GetBucketLocation",
                "s3:ListAllMyBuckets",
            ],
            "Effect": "Allow",
            "Resource": ["arn:aws:s3:::*"],
        },
    ],
}

READ_ACTIONS = [
    's3:GetObject',
    's3:GetObjectAcl',
    's3:GetObjectVersion',
]

WRITE_ACTIONS = [
    's3:DeleteObject',
    's3:DeleteObjectVersion',
    's3:PutObject',
    's3:PutObjectAcl',
    's3:RestoreObject',
]

BASE_S3_ACCESS_STATEMENT = {
    'list': {
        'Sid': 'list',
        'Action': [
            's3:ListBucket',
        ],
        'Effect': 'Allow',
    },
    'readonly': {
        'Sid': 'readonly',
        'Action': READ_ACTIONS,
        'Effect': 'Allow',
    },
    'readwrite': {
        'Sid': 'readwrite',
        'Action': READ_ACTIONS + WRITE_ACTIONS,
        'Effect': 'Allow',
    },
}


def create_app_role(app):
    iam = boto3.resource('iam')
    try:
        return iam.create_role(
            RoleName=app.iam_role_name,
            AssumeRolePolicyDocument=json.dumps(BASE_ASSUME_ROLE_POLICY),
        )
    except iam.meta.client.exceptions.EntityAlreadyExistsException:
        log.warning(f'Skipping creating Role {app.iam_role_name}: Already exists')


def create_user_role(user):
    policy = deepcopy(BASE_ASSUME_ROLE_POLICY)
    policy['Statement'].append(SAML_STATEMENT)
    oidc_statement = deepcopy(OIDC_STATEMENT)
    oidc_statement['Condition'] = {'StringEquals': {
        f'{settings.OIDC_DOMAIN}/:sub': user.auth0_id,
    }}
    policy['Statement'].append(oidc_statement)

    iam = boto3.resource('iam')
    try:
        iam.create_role(
            RoleName=user.iam_role_name,
            AssumeRolePolicyDocument=json.dumps(policy),
        )
    except iam.meta.client.exceptions.EntityAlreadyExistsException:
        log.warning(f'Skipping creating Role {user.iam_role_name}: Already exists')

    role = iam.Role(user.iam_role_name)
    role.attach_policy(
        PolicyArn=iam_arn(f"policy/{READ_INLINE_POLICIES}"),
    )


def delete_role(name):
    """Delete the given IAM role and all inline policies"""
    try:
        role = boto3.resource('iam').Role(name)
        role.load()
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            log.warning(f'Skipping delete of Role {name}: Does not exist')
            return
        raise e

    for policy in role.attached_policies.all():
        role.detach_policy(PolicyArn=policy.arn)

    for policy in role.policies.all():
        policy.delete()

    role.delete()


def create_bucket(bucket_name, is_data_warehouse=False):
    s3_resource = boto3.resource("s3")
    s3_client = boto3.client('s3')
    try:
        bucket = s3_resource.create_bucket(
            Bucket=bucket_name,
            ACL='private',
            CreateBucketConfiguration={
                'LocationConstraint': settings.BUCKET_REGION,
            },
        )
        # Enable versioning by default.
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html?highlight=s3#S3.BucketVersioning
        versioning = bucket.Versioning()
        versioning.enable()
        # Set bucket lifecycle. Send non-current versions of files to glacier
        # storage after 30 days.
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_bucket_lifecycle_configuration
        lifecycle_id = f"{bucket_name}_lifecycle_configuration"
        lifecycle_conf = s3_client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": lifecycle_id,
                        "Status": "Enabled",
                        "Prefix": "",
                        "NoncurrentVersionTransitions": [
                            {
                                'NoncurrentDays': 30,
                                'StorageClass': 'GLACIER',
                            },
                        ]
                    },
                ]
            }
        )
        if is_data_warehouse:
            _tag_bucket(bucket, {"buckettype": "datawarehouse"})

    except s3_resource.meta.client.exceptions.BucketAlreadyOwnedByYou:
        log.warning(f'Skipping creating Bucket {bucket_name}: Already exists')
        return

    bucket.Logging().put(BucketLoggingStatus={'LoggingEnabled': {
        'TargetBucket': settings.LOGS_BUCKET_NAME,
        'TargetPrefix': f"{bucket_name}/",
    }})
    bucket.meta.client.put_bucket_encryption(
        Bucket=bucket_name,
        ServerSideEncryptionConfiguration={'Rules': [{
            'ApplyServerSideEncryptionByDefault': {
                'SSEAlgorithm': 'AES256',
            },
        }]},
    )
    bucket.meta.client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': True,
            'IgnorePublicAcls': True,
            'BlockPublicPolicy': True,
            'RestrictPublicBuckets': True,
        },
    )
    return bucket


def tag_bucket(bucket_name, tags):
    """Add the given `tags` to the S3 bucket called `bucket_name`"""

    bucket = boto3.resource("s3").Bucket(bucket_name)
    _tag_bucket(bucket, tags)


def _tag_bucket(boto_bucket, tags):
    """
    Tags the bucket with the given tags

    - `boto_bucket` is boto resource
    - `tags` is a dictionary

    NOTE: The tags provided are merged with existing tags (if any)

    example:

    existing tags : {"buckettype": "datawarehouse"}
    new tags: {"to-archive": "true"}
    result: {"buckettype": "datawarehouse", "to-archive": "true"}

    example:

    existing tags : {"colour": "red", "foo": "bar"}
    new tags: {"colour": "BLUE", "buckettype": "datawarehouse"}
    result: {"colour": "BLUE", "foo": "bar", "buckettype": "datawarehouse"}
    """

    tagging = boto_bucket.Tagging()

    # Get existing tag set
    existing_tag_set = []
    try:
        existing_tag_set = tagging.tag_set
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchTagSet":
            existing_tag_set = []
        else:
            raise e

    # merge existing tags with new ones - new have precedence
    tags_existing = { tag["Key"]: tag["Value"] for tag in existing_tag_set }
    tags_new = { **tags_existing, **tags }

    # convert dictionary to boto/TagSet list/format
    tag_set = [ {"Key": k, "Value": v} for k, v in tags_new.items() ]

    # Update tags
    tagging.put(Tagging={"TagSet": tag_set})


class S3AccessPolicy:
    """Provides a convenience wrapper around a RolePolicy object"""

    def __init__(self, policy):
        self.policy = policy
        self.statements = {}

        try:
            self.policy_document = self.load_policy_document()

        except self.policy.meta.client.exceptions.NoSuchEntityException:
            # create an empty s3 access policy
            self.policy_document = deepcopy(BASE_S3_ACCESS_POLICY)
            self.put(policy_document=self.policy_document)

        # ensure version is set
        self.policy_document['Version'] = '2012-10-17'

        # ensure statements are correctly configured and build a lookup table
        self.policy_document.setdefault('Statement', [])
        for stmt in self.policy_document['Statement']:
            sid = stmt.get('Sid')
            if sid in ('list', 'readonly', 'readwrite'):
                stmt.update(deepcopy(BASE_S3_ACCESS_STATEMENT[sid]))
                self.statements[sid] = stmt

    def load_policy_document(self):
        # triggers API call
        return self.policy.policy_document

    def statement(self, sid):
        if sid in ('list', 'readonly', 'readwrite'):
            if sid not in self.statements:
                stmt = deepcopy(BASE_S3_ACCESS_STATEMENT[sid])
                self.statements[sid] = stmt
                self.policy_document['Statement'].append(stmt)
            return self.statements[sid]

    def add_resource(self, arn, sid):
        statement = self.statement(sid)
        if statement:
            statement['Resource'] = statement.get('Resource', [])
            if arn not in statement['Resource']:
                statement['Resource'].append(arn)

    def remove_resource(self, arn, sid):
        statement = self.statement(sid)
        if statement:
            resources = statement.get('Resource', [])
            for resource in list(resources):
                if resource.startswith(arn):
                    resources.remove(resource)

    def grant_object_access(self, arn, access_level):
        self.add_resource(f'{arn}/*', access_level)

    def grant_list_access(self, arn):
        self.add_resource(arn, 'list')

    def revoke_access(self, arn):
        self.remove_resource(arn, 'readonly')
        self.remove_resource(arn, 'readwrite')
        self.remove_resource(arn, 'list')

    def put(self, policy_document=None):
        if policy_document is None:
            policy_document = self.policy_document

        # remove statements with no resources
        policy_document['Statement'][:] = [
            stmt for stmt in policy_document['Statement']
            if stmt.get('Resource')
        ]

        return self.save_policy_document(policy_document)

    def save_policy_document(self, policy_document):
        return self.policy.put(
            PolicyDocument=json.dumps(policy_document),
        )


class ManagedS3AccessPolicy(S3AccessPolicy):
    """Provides a convenience wrapper around a Policy object"""

    def load_policy_document(self):
        return self.policy.default_version.document

    def save_policy_document(self, policy_document):
        self.policy.create_version(
            PolicyDocument=json.dumps(policy_document),
            SetAsDefault=True,
        )

        for version in self.policy.versions.all():
            if version.version_id != self.policy.default_version_id:
                version.delete()

        return self


def grant_bucket_access(role_name, bucket_arn, access_level, path_arns=[]):
    if access_level not in ('readonly', 'readwrite'):
        raise ValueError("access_level must be one of 'readwrite' or 'readonly'")

    if bucket_arn and not path_arns:
        path_arns = [bucket_arn]

    role = boto3.resource('iam').Role(role_name)
    policy = S3AccessPolicy(role.Policy('s3-access'))
    policy.revoke_access(bucket_arn)
    policy.grant_list_access(bucket_arn)
    for arn in path_arns:
        policy.grant_object_access(arn, access_level)
    policy.put()


def revoke_bucket_access(role_name, bucket_arn=None):
    if not bucket_arn:
        log.warning(f'Asked to revoke {role_name} role access to nothing')
        return

    try:
        role = boto3.resource("iam").Role(role_name)
        role.load()
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            log.warning(f"Role '{role_name}' doesn't exist: Nothing to revoke")
            return
        raise e

    policy = S3AccessPolicy(role.Policy('s3-access'))
    policy.revoke_access(bucket_arn)
    policy.put()


def create_group(name, path):
    iam = boto3.resource('iam')
    try:
        iam.create_policy(
            PolicyName=name,
            Path=path,
            PolicyDocument=json.dumps(BASE_S3_ACCESS_POLICY),
        )
    except iam.meta.client.exceptions.EntityAlreadyExistsException:
        log.warning(f'Skipping creating policy {path}{name}: Already exists')


def update_group_members(group_arn, role_names):
    policy = boto3.resource('iam').Policy(group_arn)
    members = set(policy.attached_roles.all())
    existing = {member.role_name for member in members}

    for role in role_names - existing:
        policy.attach_role(RoleName=role)

    for role in existing - role_names:
        policy.detach_role(RoleName=role)


def delete_group(group_arn):
    policy = boto3.resource('iam').Policy(group_arn)
    try:
        policy.load()
    except policy.meta.client.exceptions.NoSuchEntityException:
        log.warning(f"Skipping deletion of policy {group_arn}: Does not exist")
        return

    for role in policy.attached_roles.all():
        policy.detach_role(RoleName=role.name)

    for version in policy.versions.all():
        if version.version_id != policy.default_version_id:
            version.delete()

    policy.delete()


def grant_group_bucket_access(group_policy_arn, bucket_arn, access_level, path_arns=[]):
    if access_level not in ('readonly', 'readwrite'):
        raise ValueError("access_level must be 'readonly' or 'readwrite'")

    if bucket_arn and not path_arns:
        path_arns = [bucket_arn]

    policy = boto3.resource('iam').Policy(group_policy_arn)
    policy = ManagedS3AccessPolicy(policy)
    policy.revoke_access(bucket_arn)
    policy.grant_list_access(bucket_arn)
    for arn in path_arns:
        policy.grant_object_access(arn, access_level)
    policy.put()


def revoke_group_bucket_access(group_policy_arn, bucket_arn=None):
    if not bucket_arn:
        log.warning(f'Asked to revoke {group_policy_arn} group access to nothing')
        return

    policy = boto3.resource('iam').Policy(group_policy_arn)
    policy = ManagedS3AccessPolicy(policy)
    policy.revoke_access(bucket_arn)
    policy.put()


def create_parameter(name, value, role_name, description=''):
    ssm = boto3.client('ssm', region_name=settings.BUCKET_REGION)
    try:
        ssm.put_parameter(
            Name=name,
            Value=value,
            Description=description,
            Type='SecureString',
            Tags=[{
                'Key': 'role',
                'Value':  role_name
            }],
        )
    except ssm.exceptions.ParameterAlreadyExists:
        # TODO do parameter names need to be unique across the platform?
        log.warning(
            f'Skipping creating Parameter {name} for {role_name}: Already exists'
        )


def delete_parameter(name):
    ssm = boto3.client('ssm', region_name=settings.BUCKET_REGION)
    try:
        ssm.delete_parameter(Name=name)
    except ssm.exceptions.ParameterNotFound:
        log.warning(f'Skipping deleting Parameter {name}: Does not exist')


def list_role_names(prefix="/"):
    roles = boto3.resource('iam').roles.filter(PathPrefix=prefix).all()
    return [role.name for role in list(roles)]

