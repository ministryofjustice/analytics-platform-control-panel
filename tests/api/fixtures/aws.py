import boto3
import moto
import os
import pytest
import json

from django.conf import settings


@pytest.fixture(autouse=True)
def aws_creds():
    os.environ['AWS_ACCESS_KEY_ID'] = 'test-access-key-id'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-secret-access-key'
    os.environ['AWS_SECURITY_TOKEN'] = 'test-security-token'
    os.environ['AWS_SESSION_TOKEN'] = 'test-session-token'


@pytest.yield_fixture(autouse=True)
def iam(aws_creds):
    with moto.mock_iam():
        yield boto3.Session().resource('iam')


@pytest.yield_fixture(autouse=True)
def s3(aws_creds):
    with moto.mock_s3():
        yield boto3.resource('s3')


@pytest.yield_fixture(autouse=True)
def sts(aws_creds):
    with moto.mock_sts():
        yield boto3.client('sts')


@pytest.yield_fixture(autouse=True)
def ssm(aws_creds):
    with moto.mock_ssm():
        yield boto3.client('ssm', region_name='eu-west-1')


@pytest.yield_fixture(autouse=True)
def secretsmanager(aws_creds):
    with moto.mock_secretsmanager():
        yield boto3.client('secretsmanager', region_name='eu-west-1')



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
                'Resource': ['arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/{settings.ENV}_user_*'],
            },
        ]}),
    )
    return result['Policy']


@pytest.fixture(autouse=True)
def airflow_dev_policy(iam):
    policy_name = "airflow-dev-ui-access"
    result = iam.meta.client.create_policy(
        PolicyName=policy_name,
        PolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [{
                'Sid': 'ManagedAirflowCreateWebLoginToken',
                'Effect': 'Allow',
                'Action': ['iam:CreateWebLoginToken'],
                'Resource': ['arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/{settings.ENV}_user_*'],
            },
        ]}),
    )
    return result['Policy']


@pytest.fixture(autouse=True)
def airflow_prod_policy(iam):
    policy_name = "airflow-prod-ui-access"
    result = iam.meta.client.create_policy(
        PolicyName=policy_name,
        PolicyDocument=json.dumps({
            'Version': '2012-10-17',
            'Statement': [{
                'Sid': 'ManagedAirflowCreateWebLoginToken',
                'Effect': 'Allow',
                'Action': ['iam:CreateWebLoginToken'],
                'Resource': ['arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/{settings.ENV}_user_*'],
            },
        ]}),
    )
    return result['Policy']


@pytest.fixture(autouse=True)
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

