import json
from unittest.mock import MagicMock, call, patch

from django.conf import settings
from django.test.testcases import SimpleTestCase, TestCase
from model_mommy import mommy

from control_panel_api import services
from control_panel_api.aws import aws, S3AccessPolicy
from control_panel_api.models import (
    AppS3Bucket,
)
from control_panel_api.tests import (
    POLICY_DOCUMENT_READONLY,
    POLICY_DOCUMENT_READWRITE,
    USER_IAM_ROLE_ASSUME_POLICY,
)


@patch.object(aws, 'client', MagicMock())
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

    def test_policy_document_readwrite(self):
        document = services.get_policy_document(
            'arn:aws:s3:::test-bucketname', readwrite=True)
        self.assertEqual(POLICY_DOCUMENT_READWRITE, document)

        document = services.get_policy_document(
            'arn:aws:s3:::test-bucketname', readwrite=False)
        self.assertEqual(POLICY_DOCUMENT_READONLY, document)

    def test_create_bucket(self):
        services.create_bucket('test-bucketname')

        aws.client.return_value.create_bucket.assert_called_with(
            Bucket='test-bucketname',
            CreateBucketConfiguration={
                'LocationConstraint': 'eu-test-2'
            },
            ACL='private')

        aws.client.return_value.put_bucket_logging.assert_called_with(
            Bucket='test-bucketname',
            BucketLoggingStatus={
                'LoggingEnabled': {
                    'TargetBucket': 'moj-test-logs',
                    'TargetPrefix': 'test-bucketname/'
                }
            })

        aws.client.return_value.put_bucket_encryption.assert_called_with(
            Bucket='test-bucketname',
            ServerSideEncryptionConfiguration={
                'Rules': [{
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'AES256'
                    }
                }]
            })

    def test_create_bucket_policies(self):
        services.create_bucket_policies(
            'test-bucketname',
            'arn:aws:s3:::test-bucketname')

        aws.client.return_value.create_policy.assert_has_calls([
            call(
                PolicyName='test-bucketname-readwrite',
                PolicyDocument=json.dumps(POLICY_DOCUMENT_READWRITE)),
            call(
                PolicyName='test-bucketname-readonly',
                PolicyDocument=json.dumps(POLICY_DOCUMENT_READONLY))
        ])

    def test_delete_bucket_policies(self):
        aws.client.return_value.list_entities_for_policy.return_value = {
            'PolicyRoles': [{'RoleName': 'test-role'}],
            'PolicyGroups': [{'GroupName': 'test-group'}],
            'PolicyUsers': [{'UserName': 'test-user'}]
        }

        services.delete_bucket_policies('test-bucketname')
        base = settings.IAM_ARN_BASE

        aws.client.return_value.detach_role_policy.assert_has_calls([
            call(
                PolicyArn=f'{base}:policy/test-bucketname-readwrite',
                RoleName='test-role'),
            call(
                PolicyArn=f'{base}:policy/test-bucketname-readonly',
                RoleName='test-role')
        ])

        aws.client.return_value.delete_policy.assert_has_calls([
            call(PolicyArn=f'{base}:policy/test-bucketname-readwrite'),
            call(PolicyArn=f'{base}:policy/test-bucketname-readonly')
        ])

    def test_grant_bucket_access(self):
        app = App(slug='appslug')
        s3bucket = S3Bucket(name='test-bucketname')

        policy_orig = S3AccessPolicy()
        policy_orig.grant_access('test-bucket-other')
        aws.client.return_value.get_role_policy.return_value = {
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

            aws.client.return_value.put_role_policy.assert_called_with(
                RoleName=app.iam_role_name,
                PolicyName='s3-access',
                PolicyDocument=json.dumps(policy_expected.document),
            )

    def test_revoke_bucket_access(self):
        app = App(slug='appslug')
        s3bucket = S3Bucket(name='test-bucketname')

        for readwrite in [False, True]:
            policy_orig = S3AccessPolicy()
            policy_orig.grant_access('test-bucket-other')
            policy_orig.grant_access(s3bucket.arn, readwrite=readwrite)
            aws.client.return_value.get_role_policy.return_value = {
                'PolicyDocument': policy_orig.document,
            }

            services.revoke_bucket_access(s3bucket.arn, app.iam_role_name)

            policy_expected = S3AccessPolicy(document=policy_orig.document)
            policy_expected.revoke_access(s3bucket.arn)

            aws.client.return_value.put_role_policy.assert_called_with(
                RoleName=app.iam_role_name,
                PolicyName='s3-access',
                PolicyDocument=json.dumps(policy_expected.document),
            )

    def test_create_user_role(self):
        role_name = "test_user_user"

        services.create_role(role_name, add_saml_statement=True)

        aws.client.return_value.create_role.assert_called_with(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(USER_IAM_ROLE_ASSUME_POLICY))


class NamingTestCase(SimpleTestCase):

    def test_policy_name_has_readwrite(self):
        self.assertEqual('bucketname-readonly',
                         services._policy_name('bucketname', readwrite=False))
        self.assertEqual('bucketname-readwrite',
                         services._policy_name('bucketname', readwrite=True))

    def test_policy_arn(self):
        self.assertEqual(f'{settings.IAM_ARN_BASE}:policy/bucketname-readonly',
                         services._policy_arn('bucketname', readwrite=False))
        self.assertEqual(f'{settings.IAM_ARN_BASE}:policy/bucketname-readwrite',
                         services._policy_arn('bucketname', readwrite=True))
