import json
from unittest.mock import patch

from django.conf import settings
from model_mommy import mommy
import pytest

from controlpanel.api import services
from controlpanel.api.aws import S3AccessPolicy
from controlpanel.api.models import (
    App,
    S3Bucket,
)
from tests.api import USER_IAM_ROLE_ASSUME_POLICY


@pytest.fixture
def app():
    return mommy.make('api.App', repo_url='https://example.com/app-1')


@pytest.yield_fixture
def aws():
    with patch.object(services.aws, 'client') as aws_client:
        yield aws_client.return_value


@pytest.fixture
def bucket():
    return mommy.make('api.S3Bucket', name='test-bucket-1')


def test_create_bucket(aws):
    services.create_bucket('test-bucketname', is_data_warehouse=True)

    aws.create_bucket.assert_called_with(
        Bucket='test-bucketname',
        ACL='private',
        CreateBucketConfiguration={
            'LocationConstraint': settings.BUCKET_REGION,
        },
    )

    aws.put_bucket_logging.assert_called_with(
        Bucket='test-bucketname',
        BucketLoggingStatus={
            'LoggingEnabled': {
                'TargetBucket': settings.LOGS_BUCKET_NAME,
                'TargetPrefix': "test-bucketname/",
            },
        },
    )

    aws.put_bucket_encryption.assert_called_with(
        Bucket='test-bucketname',
        ServerSideEncryptionConfiguration={
            'Rules': [
                {
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'AES256',
                    },
                },
            ],
        },
    )

    aws.put_bucket_tagging.assert_called_with(
        Bucket='test-bucketname',
        Tagging={
            'TagSet': [
                {'Key': 'buckettype', 'Value': 'datawarehouse'},
            ],
        },
    )


def test_grant_bucket_access(aws):
    app = App(slug='appslug')
    s3bucket = S3Bucket(name='test-bucketname')

    policy_orig = S3AccessPolicy()
    policy_orig.grant_access('test-bucket-other')
    aws.get_role_policy.return_value = {
        'PolicyDocument': policy_orig.document,
    }

    for readwrite in [False, True]:
        services.grant_bucket_access(
            s3bucket.arn,
            readwrite,
            app.iam_role_name
        )

        policy_expected = S3AccessPolicy(document=policy_orig.document)
        policy_expected.grant_access(s3bucket.arn, readwrite=readwrite)

        aws.put_role_policy.assert_called_with(
            RoleName=app.iam_role_name,
            PolicyName='s3-access',
            PolicyDocument=json.dumps(policy_expected.document),
        )


def test_revoke_bucket_access(aws):
    app = App(slug='appslug')
    s3bucket = S3Bucket(name='test-bucketname')

    for readwrite in [False, True]:
        policy_orig = S3AccessPolicy()
        policy_orig.grant_access('test-bucket-other')
        policy_orig.grant_access(s3bucket.arn, readwrite=readwrite)
        aws.get_role_policy.return_value = {
            'PolicyDocument': policy_orig.document,
        }

        services.revoke_bucket_access(s3bucket.arn, app.iam_role_name)

        policy_expected = S3AccessPolicy(document=policy_orig.document)
        policy_expected.revoke_access(s3bucket.arn)

        aws.put_role_policy.assert_called_with(
            RoleName=app.iam_role_name,
            PolicyName='s3-access',
            PolicyDocument=json.dumps(policy_expected.document),
        )


def test_create_user_role(aws):
    role_name = "test_user_user"

    services.create_role(
        role_name,
        add_saml_statement=True,
        add_oidc_statement=True,
        oidc_sub="github|user_1",
    )

    aws.create_role.assert_called_with(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(USER_IAM_ROLE_ASSUME_POLICY),
    )


def test_grant_read_inline_policies(aws):
    role_name = "test_user_user"
    services.grant_read_inline_policies(role_name)

    aws.attach_role_policy.assert_called_with(
        RoleName=role_name,
        PolicyArn=(
            f'{settings.IAM_ARN_BASE}:policy/'
            f'{settings.ENV}-read-user-roles-inline-policies'
        ),
    )
