import json
import os
from unittest.mock import MagicMock

import boto3
from django.conf import settings
from model_mommy import mommy
import moto
import pytest

from controlpanel.api import aws


@pytest.yield_fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture(autouse=True)
def aws_creds():
    os.environ['AWS_ACCESS_KEY_ID'] = 'test-access-key-id'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-secret-access-key'
    os.environ['AWS_SECURITY_TOKEN'] = 'test-security-token'
    os.environ['AWS_SESSION_TOKEN'] = 'test-session-token'


@pytest.yield_fixture(autouse=True)
def iam(aws_creds):
    with moto.mock_iam():
        yield boto3.resource('iam')


@pytest.yield_fixture(autouse=True)
def s3(aws_creds):
    with moto.mock_s3():
        yield boto3.resource('s3')


@pytest.yield_fixture(autouse=True)
def ssm(aws_creds):
    with moto.mock_ssm():
        yield boto3.client('ssm', region_name='eu-west-1')


@pytest.fixture(autouse=True)
def managed_policy(iam):
    result = iam.meta.client.create_policy(
        PolicyName='test-read-user-roles-inline-policies',
        PolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [{
                'Sid': 'CanReadUserRolesInlinePolicies',
                'Effect': 'Allow',
                'Action': ['iam:GetRolePolicy'],
                'Resource': ['arn:aws:iam::{settings.AWS_ACCOUNT_ID}:role/{settings.ENV}_user_*'],
            },
        ]}),
    )
    return result['Policy']


def stmt_match(stmt, Action='sts:AssumeRole', Condition=None, Effect='Allow', Principal={}):
    result = stmt['Action'] == Action
    if Condition:
        result = result and stmt['Condition'] == Condition
    result = result and stmt['Effect'] == Effect
    result = result and stmt['Principal'] == Principal
    return result


def ec2_assume_role(stmt):
    return stmt_match(stmt, Principal={'Service': 'ec2.amazonaws.com'})


def k8s_assume_role(stmt):
    return stmt_match(
        stmt,
        Principal={
            'AWS': f'arn:aws:iam::{settings.AWS_ACCOUNT_ID}:role/{settings.K8S_WORKER_ROLE_NAME}',
        },
    )


def saml_assume_role(stmt):
    return stmt_match(
        stmt,
        Action='sts:AssumeRoleWithSAML',
        Principal={
            'Federated': f'arn:aws:iam::{settings.AWS_ACCOUNT_ID}:saml-provider/{settings.SAML_PROVIDER}',
        },
        Condition={
            'StringEquals': {'SAML:aud': 'https://signin.aws.amazon.com/saml'},
        },
    )


def oidc_assume_role(stmt, user):
    return stmt_match(
        stmt,
        Action='sts:AssumeRoleWithWebIdentity',
        Principal={
            'Federated': f"arn:aws:iam::{settings.AWS_ACCOUNT_ID}:oidc-provider/{settings.OIDC_DOMAIN}/",
        },
        Condition={
            'StringEquals': {f"{settings.OIDC_DOMAIN}/:sub": user.auth0_id},
        },
    )


@pytest.fixture
def roles(iam):
    role_names = [
        'test_app_test-app',
        'test_user_normal-user',
    ]
    for role_name in role_names:
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "test.amazonaws.com"},
                }],
            }),
        )


@pytest.fixture
def app():
    return mommy.make('api.App', slug='test-app')


def test_create_app_role(iam, app):
    aws.create_app_role(app)

    role = iam.Role(app.iam_role_name)
    pd = role.assume_role_policy_document
    assert len(pd['Statement']) == 2
    assert ec2_assume_role(pd['Statement'][0])
    assert k8s_assume_role(pd['Statement'][1])


def test_create_user_role(iam, managed_policy, users):
    user = users['normal_user']

    aws.create_user_role(user)

    role = iam.Role(user.iam_role_name)
    pd = role.assume_role_policy_document

    assert len(pd['Statement']) == 4
    assert ec2_assume_role(pd['Statement'][0])
    assert k8s_assume_role(pd['Statement'][1])
    assert saml_assume_role(pd['Statement'][2])
    assert oidc_assume_role(pd['Statement'][3], user)

    attached_policies = list(role.attached_policies.all())
    assert len(attached_policies) == 1
    assert attached_policies[0].arn == managed_policy['Arn']


@pytest.fixture
def role_policy():
    def make_role_policy(role):
        policy = role.Policy('test')
        policy.put(PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "s3:ListAllMyBuckets",
                "Effect": "Allow",
                "Resource": "arn:aws:s3:::*",
            }],
        }))
        return policy
    return make_role_policy


# TODO parametrize cases:
#   - role does not exist
def test_delete_role(iam, managed_policy, role_policy, users):
    user = users['normal_user']

    aws.create_user_role(user)

    role = iam.Role(user.iam_role_name)
    inline_policy = role_policy(role)

    attached_policy = iam.Policy(managed_policy['Arn'])
    assert attached_policy.attachment_count == 1

    aws.delete_role(user.iam_role_name)

    with pytest.raises(iam.meta.client.exceptions.NoSuchEntityException):
        role.load()

    with pytest.raises(iam.meta.client.exceptions.NoSuchEntityException):
        inline_policy.load()

    attached_policy.reload()
    assert attached_policy.attachment_count == 0


@pytest.fixture
def logs_bucket(s3):
    bucket = s3.Bucket(settings.LOGS_BUCKET_NAME)
    bucket.create(CreateBucketConfiguration={
        "LocationConstraint": settings.BUCKET_REGION,
    })
    bucket.Acl().put(AccessControlPolicy={
        'Grants': [
            {
                "Grantee": {
                    "URI": 'http://acs.amazonaws.com/groups/s3/LogDelivery',
                    "Type": "Group",
                },
                "Permission": "WRITE",
            },
            {
                "Grantee": {
                    "Type": "Group",
                    "URI": 'http://acs.amazonaws.com/groups/s3/LogDelivery',
                },
                "Permission": "READ_ACP",
            },
        ],
        "Owner": bucket.Acl().owner,
    })


def test_create_bucket(logs_bucket, s3):
    bucket_name = f'bucket-{id(MagicMock())}'
    bucket = s3.Bucket(bucket_name)

    with pytest.raises(s3.meta.client.exceptions.NoSuchBucket):
        s3.meta.client.get_bucket_location(Bucket=bucket_name)

    aws.create_bucket(bucket_name, is_data_warehouse=True)

    bucket.load()
    assert bucket.Logging().logging_enabled['TargetBucket'] == settings.LOGS_BUCKET_NAME
    # XXX moto 1.3.10 doesn't provide get_bucket_encryption(),
    # get_public_access_block() or get_bucket_tagging() yet
    # assert encrypted(bucket, alg='AES256')
    # assert public_access_blocked(bucket)
    # assert tagged(bucket, buckettype=datawarehouse)


def test_create_parameter(ssm):
    aws.create_parameter(
        "test",
        "test_val",
        "role_name",
        description="test desc"
    )

    param = ssm.get_parameter(Name="test", WithDecryption=True)['Parameter']
    assert param['Value'] == 'test_val'


def test_delete_parameter(ssm):
    aws.delete_parameter("test")

    with pytest.raises(ssm.exceptions.ParameterNotFound):
        ssm.get_parameter(Name="test")


def get_statements_by_sid(policy_document):
    statements = {}
    for statement in policy_document['Statement']:
        sid = statement.get('Sid')
        if sid:
            statements[sid] = statement
    return statements


@pytest.mark.parametrize(
    'resources',
    [
        ([],),
        (['/foo/bar', '/foo/baz']),
    ],
    ids=[
        'no-paths',
        'paths',
    ],
)
def test_grant_bucket_access(iam, users, resources):
    bucket_arn = 'arn:aws:s3:::test-bucket'
    path_arns = [f'{bucket_arn}{resource}' for resource in resources]
    user = users['normal_user']
    aws.create_user_role(user)

    aws.grant_bucket_access(user.iam_role_name, bucket_arn, 'readonly', path_arns)

    policy = iam.RolePolicy(user.iam_role_name, 's3-access')
    statements = get_statements_by_sid(policy.policy_document)

    if path_arns:
        assert f'{bucket_arn}/*' not in statements['readonly']['Resource']
    else:
        assert f'{bucket_arn}/*' in statements['readonly']['Resource']
    # no readwrite statement because no readwrite access granted
    assert 'readwrite' not in statements
    if path_arns:
        assert set(path_arns) == set(statements['list']['Resource'])
    else:
        assert bucket_arn in statements['list']['Resource']

    aws.grant_bucket_access(user.iam_role_name, f'{bucket_arn}-2', 'readonly')
    policy.reload()
    statements = get_statements_by_sid(policy.policy_document)
    expected_num_resources = 2
    if path_arns:
        expected_num_resources = len(path_arns) + 1
    assert len(statements['readonly']['Resource']) == expected_num_resources


@pytest.mark.parametrize(
    'resources',
    [
        ([],),
        (['/foo/bar', '/foo/baz']),
    ],
    ids=[
        'no-paths',
        'paths',
    ],
)
def test_revoke_bucket_access(iam, users, resources):
    bucket_arn = 'arn:aws:s3:::test-bucket'
    path_arns = [f'{bucket_arn}{resource}' for resource in resources]
    user = users['normal_user']
    aws.create_user_role(user)
    aws.grant_bucket_access(user.iam_role_name, bucket_arn, 'readonly', path_arns)

    aws.revoke_bucket_access(user.iam_role_name, bucket_arn, path_arns)

    policy = iam.RolePolicy(user.iam_role_name, 's3-access')
    statements = get_statements_by_sid(policy.policy_document)
    assert 'readonly' not in statements
    assert 'readwrite' not in statements
    assert 'list' not in statements


def test_create_group(iam, settings):
    aws.create_group('test', '/group/test/')

    policy = iam.Policy(f'arn:aws:iam::{settings.AWS_ACCOUNT_ID}:policy/group/test/test')
    pd = policy.default_version.document
    stmt = pd['Statement'][0]
    assert stmt['Action'] == [
        's3:GetBucketLocation',
        's3:ListAllMyBuckets',
    ]
    assert stmt['Resource'] == ['arn:aws:s3:::*']
    assert stmt['Effect'] == 'Allow'


def assert_group_members(policy, role_names):
    attached_roles = list(policy.attached_roles.all())
    assert len(attached_roles) == len(role_names)
    for role, role_name in zip(attached_roles, role_names):
        assert role.role_name == role_name


@pytest.fixture
def user_roles(iam, users):
    for user in users.values():
        aws.create_user_role(user)


@pytest.fixture
def group(iam):
    aws.create_group('test', '/group/test/')
    group_arn = f'arn:aws:iam::{settings.AWS_ACCOUNT_ID}:policy/group/test/test'
    return iam.Policy(group_arn)


@pytest.mark.parametrize(
    'live, stored',
    [
        ([], ['test_user_alice']),
        (['test_user_bob'], ['test_user_alice', 'test_user_bob']),
        (['test_user_bob', 'test_user_carol'], ['test_user_bob']),
    ],
    ids=[
        'new-group',
        'add-members',
        'remove-members',
    ],
)
def test_update_group_members(iam, group, users, user_roles, live, stored):
    aws.update_group_members(group.arn, set(live))
    assert_group_members(group, live)

    aws.update_group_members(group.arn, set(stored))
    assert_group_members(group, stored)


def test_delete_group(iam, group, user_roles):
    role = iam.Role('test_user_alice')
    aws.update_group_members(group.arn, set([role.name]))

    assert len(list(role.attached_policies.all())) == 2

    try:
        aws.delete_group(group.arn)

    except NotImplementedError as e:
        if 'delete_policy' in str(e):
            # moto 1.3.13 doesn't mock delete_policy yet
            pass

    # with pytest.raises(iam.meta.client.exceptions.NoSuchEntityException):
    #     iam.Policy(group_arn).load()

    assert len(list(role.attached_policies.all())) == 1


@pytest.mark.parametrize(
    'resources',
    [
        ([],),
        (['/foo/bar', '/foo/baz']),
    ],
    ids=[
        'no-paths',
        'paths',
    ],
)
def test_grant_group_bucket_access(iam, group, resources):
    bucket_arn = 'arn:aws:s3:::test-bucket'
    path_arns = [f'{bucket_arn}{resource}' for resource in resources]

    aws.grant_group_bucket_access(group.arn, bucket_arn, 'readonly', path_arns)

    group.reload()
    statements = get_statements_by_sid(group.default_version.document)

    if path_arns:
        assert f'{bucket_arn}/*' not in statements['readonly']['Resource']
    else:
        assert f'{bucket_arn}/*' in statements['readonly']['Resource']
    assert 'readwrite' not in statements
    if path_arns:
        assert set(path_arns) == set(statements['list']['Resource'])
    else:
        assert bucket_arn in statements['list']['Resource']


@pytest.mark.parametrize(
    'resources',
    [
        ([],),
        (['/foo/bar', '/foo/baz']),
    ],
    ids=[
        'no-paths',
        'paths',
    ],
)
def test_revoke_group_bucket_access(iam, group, resources):
    bucket_arn = 'arn:aws:s3:::test-bucket'
    path_arns = [
        f'{bucket_arn}{resource}'
        for resource in resources
    ]
    aws.grant_group_bucket_access(group.arn, bucket_arn, 'readonly', path_arns)

    aws.revoke_group_bucket_access(group.arn, bucket_arn, path_arns)

    group.reload()
    statements = get_statements_by_sid(group.default_version.document)

    assert 'readonly' not in statements
    assert 'readwrite' not in statements
    assert 'list' not in statements
