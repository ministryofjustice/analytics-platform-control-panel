from unittest.mock import patch, call

from django.test.testcases import SimpleTestCase

from control_panel_api import services
from control_panel_api.tests import (
    APP_IAM_ROLE_ASSUME_POLICY,
    IAM_ARN_BASE,
    POLICY_DOCUMENT_READONLY,
    POLICY_DOCUMENT_READWRITE,
)


class ServicesTestCase(SimpleTestCase):

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
        mock_put_bucket_logging.assert_called_with('test-bucketname', target_bucket='moj-test-logs',
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
    def test_delete_bucket_policies(self, mock_detach_policy_from_entities, mock_delete_policy):
        services.delete_bucket_policies('test-bucketname')

        expected_calls = [
            call(f'{IAM_ARN_BASE}:policy/test-bucketname-readwrite'),
            call(f'{IAM_ARN_BASE}:policy/test-bucketname-readonly')
        ]
        mock_detach_policy_from_entities.assert_has_calls(expected_calls)

        expected_calls = [
            call(f'{IAM_ARN_BASE}:policy/test-bucketname-readwrite'),
            call(f'{IAM_ARN_BASE}:policy/test-bucketname-readonly')
        ]
        mock_delete_policy.assert_has_calls(expected_calls)

    @patch('control_panel_api.services.create_bucket')
    @patch('control_panel_api.services.create_bucket_policies')
    def test_bucket_create(self, mock_create_bucket_policies, mock_create_bucket):
        services.bucket_create('test-bucketname')

        mock_create_bucket_policies.assert_called()
        mock_create_bucket.assert_called()

    @patch('control_panel_api.services.delete_bucket_policies')
    def test_bucket_delete(self, mock_delete_bucket_policies):
        services.bucket_delete('test-bucketname')

        mock_delete_bucket_policies.assert_called()

    @patch('control_panel_api.aws.create_role')
    def test_app_create(self, mock_create_role):
        app_slug = 'appname'
        services.app_create(app_slug)

        expected_role_name = "test_app_{}".format(app_slug)

        mock_create_role.assert_called_with(
            expected_role_name, APP_IAM_ROLE_ASSUME_POLICY)

    @patch('control_panel_api.aws.delete_role')
    def test_app_delete(self, mock_delete_role):
        app_slug = 'appname'
        services.app_delete(app_slug)

        expected_role_name = "test_app_{}".format(app_slug)

        mock_delete_role.assert_called_with(expected_role_name)


class NamingTestCase(SimpleTestCase):

    def test_policy_name_has_readwrite(self):
        self.assertEqual('bucketname-readonly',
                         services._policy_name('bucketname', readwrite=False))
        self.assertEqual('bucketname-readwrite',
                         services._policy_name('bucketname', readwrite=True))

    def test_policy_arn(self):
        self.assertEqual(f'{IAM_ARN_BASE}:policy/bucketname-readonly',
                         services._policy_arn('bucketname', readwrite=False))
        self.assertEqual(f'{IAM_ARN_BASE}:policy/bucketname-readwrite',
                         services._policy_arn('bucketname', readwrite=True))

    def test_bucket_arn(self):
        self.assertEqual('arn:aws:s3:::bucketname',
                         services.bucket_arn('bucketname'))
