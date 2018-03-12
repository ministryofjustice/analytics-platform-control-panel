import json
from unittest.mock import call, patch

from django.conf import settings
from django.test.testcases import SimpleTestCase, TestCase
from model_mommy import mommy

from control_panel_api import services
from control_panel_api.aws import aws, S3AccessPolicy
from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
)
from control_panel_api.tests import USER_IAM_ROLE_ASSUME_POLICY


@patch('control_panel_api.aws.aws.client')
class ServicesTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.app_1 = mommy.make(
            'control_panel_api.App',
            repo_url='https://example.com/app-1'
        )
        self.s3_bucket_1 = mommy.make(
            'control_panel_api.S3Bucket',
            name='test-bucket-1')

    def test_create_bucket(self, mock_client):
        services.create_bucket('test-bucketname', is_data_warehouse=True)

        mock_client.return_value.create_bucket.assert_called_with(
            Bucket='test-bucketname',
            CreateBucketConfiguration={
                'LocationConstraint': 'eu-test-2'
            },
            ACL='private')

        mock_client.return_value.put_bucket_logging.assert_called_with(
            Bucket='test-bucketname',
            BucketLoggingStatus={
                'LoggingEnabled': {
                    'TargetBucket': 'moj-test-logs',
                    'TargetPrefix': 'test-bucketname/'
                }
            })

        mock_client.return_value.put_bucket_encryption.assert_called_with(
            Bucket='test-bucketname',
            ServerSideEncryptionConfiguration={
                'Rules': [{
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'AES256'
                    }
                }]
            })

        mock_client.return_value.put_bucket_tagging.assert_called_with(
            Bucket='test-bucketname',
            Tagging={
                'TagSet': [{
                    'Key': 'buckettype',
                    'Value': 'datawarehouse'
                }]
            })

    def test_grant_bucket_access(self, mock_client):
        app = App(slug='appslug')
        s3bucket = S3Bucket(name='test-bucketname')

        policy_orig = S3AccessPolicy()
        policy_orig.grant_access('test-bucket-other')
        mock_client.return_value.get_role_policy.return_value = {
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

            mock_client.return_value.put_role_policy.assert_called_with(
                RoleName=app.iam_role_name,
                PolicyName='s3-access',
                PolicyDocument=json.dumps(policy_expected.document),
            )

    def test_revoke_bucket_access(self, mock_client):
        app = App(slug='appslug')
        s3bucket = S3Bucket(name='test-bucketname')

        for readwrite in [False, True]:
            policy_orig = S3AccessPolicy()
            policy_orig.grant_access('test-bucket-other')
            policy_orig.grant_access(s3bucket.arn, readwrite=readwrite)
            mock_client.return_value.get_role_policy.return_value = {
                'PolicyDocument': policy_orig.document,
            }

            services.revoke_bucket_access(s3bucket.arn, app.iam_role_name)

            policy_expected = S3AccessPolicy(document=policy_orig.document)
            policy_expected.revoke_access(s3bucket.arn)

            mock_client.return_value.put_role_policy.assert_called_with(
                RoleName=app.iam_role_name,
                PolicyName='s3-access',
                PolicyDocument=json.dumps(policy_expected.document),
            )

    def test_create_user_role(self, mock_client):
        role_name = "test_user_user"

        services.create_role(
            role_name, add_saml_statement=True, add_oidc_statement=True,
            oidc_sub="github|user_1")

        mock_client.return_value.create_role.assert_called_with(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(USER_IAM_ROLE_ASSUME_POLICY))
