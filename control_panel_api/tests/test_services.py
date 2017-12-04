import json
from unittest.mock import MagicMock, patch, call

from django.conf import settings
from django.test.testcases import SimpleTestCase, TestCase
from model_mommy import mommy

from control_panel_api import services
from control_panel_api.aws import aws
from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
)
from control_panel_api.tests import (
    POLICY_DOCUMENT_READONLY,
    POLICY_DOCUMENT_READWRITE,
    USER_IAM_ROLE_ASSUME_POLICY)


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

    def test_apps3bucket_create(self):
        app = mommy.make('control_panel_api.App', slug='appslug')
        s3bucket = mommy.make(
            'control_panel_api.S3Bucket', name='test-bucketname')

        for access_level in ['readonly', 'readwrite']:
            apps3bucket, _ = AppS3Bucket.objects.update_or_create(
                app=app,
                s3bucket=s3bucket,
                defaults={'access_level': access_level},
            )

            services.attach_bucket_access_to_role(
                apps3bucket.s3bucket.name,
                apps3bucket.has_readwrite_access(),
                apps3bucket.app.iam_role_name
            )

            expected_policy_arn = f'{settings.IAM_ARN_BASE}:policy/test-bucketname-{access_level}'
            expected_role_name = f'test_app_{app.slug}'

            aws.client.return_value.attach_role_policy.assert_called_with(
                PolicyArn=expected_policy_arn,
                RoleName=expected_role_name,
            )


    def test_apps3bucket_update(self):
        app = mommy.make('control_panel_api.App', slug='appslug')
        s3bucket = mommy.make(
            'control_panel_api.S3Bucket', name='test-bucketname')

        app_role_name = f'test_app_{app.slug}'

        for access_level in ['readonly', 'readwrite']:
            apps3bucket, _ = AppS3Bucket.objects.update_or_create(
                app=app,
                s3bucket=s3bucket,
                defaults={'access_level': access_level},
            )
            services.update_bucket_access(
                s3bucket.name,
                apps3bucket.has_readwrite_access(),
                app.iam_role_name
            )

            old_access_level = 'readwrite' if access_level == 'readonly' else 'readonly'
            new_policy_arn = f'{settings.IAM_ARN_BASE}:policy/test-bucketname-{access_level}'
            old_policy_arn = f'{settings.IAM_ARN_BASE}:policy/test-bucketname-{old_access_level}'

            aws.client.return_value.attach_role_policy.assert_called_with(
                PolicyArn=new_policy_arn,
                RoleName=app_role_name)

            aws.client.return_value.detach_role_policy.assert_called_with(
                PolicyArn=old_policy_arn,
                RoleName=app_role_name)

    def test_detach_bucket_access_from_app_role_readwrite(self):
        services.detach_bucket_access_from_role(
            self.s3_bucket_1.name,
            services.READWRITE,
            self.app_1.iam_role_name,
        )

        aws.client.return_value.detach_role_policy(
            PolicyArn=f'{settings.IAM_ARN_BASE}:policy/test-bucket-1-readwrite',
            RoleName='test_app_app-1')

    def test_detach_bucket_access_from_app_role_readonly(self):

        services.detach_bucket_access_from_role(
            self.s3_bucket_1.name,
            False,
            self.app_1.iam_role_name,
        )

        aws.client.return_value.detach_role_policy.assert_called_with(
            PolicyArn=f'{settings.IAM_ARN_BASE}:policy/test-bucket-1-readonly',
            RoleName='test_app_app-1')

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
