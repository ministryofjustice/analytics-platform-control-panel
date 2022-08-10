import boto3
import moto
import os
import pytest


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
def ssm(aws_creds):
    with moto.mock_ssm():
        yield boto3.client('ssm', region_name='eu-west-1')


@pytest.yield_fixture(autouse=True)
def secretsmanager(aws_creds):
    with moto.mock_secretsmanager():
        yield boto3.client('secretsmanager', region_name='eu-west-1')

