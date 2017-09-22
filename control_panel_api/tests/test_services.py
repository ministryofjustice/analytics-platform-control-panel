from unittest.mock import patch, call

from django.conf import settings
from django.test.testcases import SimpleTestCase, TestCase
from model_mommy import mommy

from control_panel_api import services
from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
)
from control_panel_api.tests import (
    APP_IAM_ROLE_ASSUME_POLICY,
    POLICY_DOCUMENT_READONLY,
    POLICY_DOCUMENT_READWRITE,
)


class ServicesTestCase(TestCase):
    def setUp(self):
        self.app_1 = mommy.make('control_panel_api.App', name='app-1')
        self.s3_bucket_1 = mommy.make('control_panel_api.S3Bucket',
                                      name='test-bucket-1')

    def test_policy_document_readwrite(self):
        document = services.get_policy_document(
            'test-bucketname', readwrite=True)
        self.assertEqual(POLICY_DOCUMENT_READWRITE, document)

        document = services.get_policy_document(
            'test-bucketname', readwrite=False)
        self.assertEqual(POLICY_DOCUMENT_READONLY, document)

    @patch('control_panel_api.aws.put_bucket_logging')
    @patch('control_panel_api.aws.create_bucket')
    def test_create_bucket(self, mock_create_bucket, mock_put_bucket_logging):
        services.create_bucket('test-bucketname')

        mock_create_bucket.assert_called_with(
            'test-bucketname', region='eu-test-2', acl='private')
        mock_put_bucket_logging.assert_called_with('test-bucketname',
                                                   target_bucket='moj-test-logs',
                                                   target_prefix='test-bucketname/')

    @patch('control_panel_api.aws.create_policy')
    def test_create_bucket_policies(self, mock_create_policy):
        services.create_bucket_policies('test-bucketname')

        expected_calls = [
            call('test-bucketname-readwrite', POLICY_DOCUMENT_READWRITE),
            call('test-bucketname-readonly', POLICY_DOCUMENT_READONLY),
        ]
        mock_create_policy.assert_has_calls(expected_calls)

    @patch('control_panel_api.aws.delete_policy')
    @patch('control_panel_api.aws.detach_policy_from_entities')
    def test_delete_bucket_policies(self, mock_detach_policy_from_entities,
                                    mock_delete_policy):
        services.delete_bucket_policies('test-bucketname')

        expected_calls = [
            call(f'{settings.IAM_ARN_BASE}:policy/test-bucketname-readwrite'),
            call(f'{settings.IAM_ARN_BASE}:policy/test-bucketname-readonly')
        ]
        mock_detach_policy_from_entities.assert_has_calls(expected_calls)

        expected_calls = [
            call(f'{settings.IAM_ARN_BASE}:policy/test-bucketname-readwrite'),
            call(f'{settings.IAM_ARN_BASE}:policy/test-bucketname-readonly')
        ]
        mock_delete_policy.assert_has_calls(expected_calls)

    @patch('control_panel_api.services.create_bucket')
    @patch('control_panel_api.services.create_bucket_policies')
    def test_bucket_create(self, mock_create_bucket_policies,
                           mock_create_bucket):
        services.bucket_create('test-bucketname')

        mock_create_bucket_policies.assert_called()
        mock_create_bucket.assert_called()

    @patch('control_panel_api.services.delete_bucket_policies')
    def test_bucket_delete(self, mock_delete_bucket_policies):
        services.bucket_delete('test-bucketname')

        mock_delete_bucket_policies.assert_called()

    @patch('control_panel_api.aws.attach_policy_to_role')
    def test_apps3bucket_create(self, mock_attach_policy_to_role):
        app = App.objects.create(slug='appslug')
        s3bucket = S3Bucket.objects.create(name='test-bucketname')

        for access_level in ['readonly', 'readwrite']:
            apps3bucket, _ = AppS3Bucket.objects.update_or_create(
                app=app,
                s3bucket=s3bucket,
                defaults={'access_level': access_level},
            )

            services.apps3bucket_create(apps3bucket)

            expected_policy_arn = f'{settings.IAM_ARN_BASE}:policy/test-bucketname-{access_level}'
            expected_role_name = f'test_app_{app.slug}'

            mock_attach_policy_to_role.assert_called_with(
                policy_arn=expected_policy_arn,
                role_name=expected_role_name,
            )

    @patch('control_panel_api.aws.attach_policy_to_role')
    @patch('control_panel_api.aws.detach_policy_from_role')
    def test_apps3bucket_update(self,
            mock_detach_policy_from_role,
            mock_attach_policy_to_role):
        app = App.objects.create(slug='appslug')
        s3bucket = S3Bucket.objects.create(name='test-bucketname')

        app_role_name = f'test_app_{app.slug}'

        for access_level in ['readonly', 'readwrite']:
            apps3bucket, _ = AppS3Bucket.objects.update_or_create(
                app=app,
                s3bucket=s3bucket,
                defaults={'access_level': access_level},
            )
            services.apps3bucket_update(apps3bucket)

            old_access_level = 'readwrite' if access_level=='readonly' else 'readonly'
            new_policy_arn = f'{settings.IAM_ARN_BASE}:policy/test-bucketname-{access_level}'
            old_policy_arn = f'{settings.IAM_ARN_BASE}:policy/test-bucketname-{old_access_level}'

            mock_attach_policy_to_role.assert_called_with(
                policy_arn=new_policy_arn,
                role_name=app_role_name,
            )
            mock_detach_policy_from_role.assert_called_with(
                policy_arn=old_policy_arn,
                role_name=app_role_name,
            )

    @patch('control_panel_api.services.detach_bucket_access_from_app_role')
    def test_apps3bucket_delete(self, mock_detach_bucket_access_from_app_role):
        app_name = 'app-2'
        s3_bucket_name = 'test-bucket-2'

        apps3bucket = mommy.make(
            'control_panel_api.AppS3Bucket',
            make_m2m=True,
            app__name=app_name,
            s3bucket__name=s3_bucket_name,
            access_level=services.READWRITE)

        services.apps3bucket_delete(apps3bucket)

        mock_detach_bucket_access_from_app_role.assert_called_with(
            app_name,
            s3_bucket_name,
            services.READWRITE)

    @patch('control_panel_api.aws.detach_policy_from_role')
    def test_detach_bucket_access_from_app_role_readwrite(
            self,
            mock_detach_policy_from_role):
        services.detach_bucket_access_from_app_role(self.app_1.slug,
                                                    self.s3_bucket_1.name,
                                                    services.READWRITE)

        mock_detach_policy_from_role.assert_called_with(
            policy_arn=f'{settings.IAM_ARN_BASE}:policy/test-bucket-1-readwrite',
            role_name='test_app_app-1')

    @patch('control_panel_api.aws.detach_policy_from_role')
    def test_detach_bucket_access_from_app_role_readonly(
            self,
            mock_detach_policy_from_role):
        services.detach_bucket_access_from_app_role(self.app_1.slug,
                                                    self.s3_bucket_1.name,
                                                    services.READONLY)

        mock_detach_policy_from_role.assert_called_with(
            policy_arn=f'{settings.IAM_ARN_BASE}:policy/test-bucket-1-readonly',
            role_name='test_app_app-1')


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

    def test_bucket_arn(self):
        self.assertEqual('arn:aws:s3:::bucketname',
                         services.bucket_arn('bucketname'))
