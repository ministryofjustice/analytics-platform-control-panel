from unittest.mock import patch, call

from django.test.testcases import SimpleTestCase, override_settings

from control_panel_api import services
from control_panel_api.tests import POLICY_DOCUMENT_READWRITE, POLICY_DOCUMENT_READONLY


@override_settings(ENV='test', BUCKET_REGION='eu-test-2', LOGS_BUCKET_NAME='moj-test-logs',
                   IAM_ARN_BASE='arn:aws:iam::1337')
class ServicesTestCase(SimpleTestCase):
    def test_policy_document_readwrite(self):
        document = services.get_policy_document('test-bucketname', readwrite=True)
        self.assertEqual(POLICY_DOCUMENT_READWRITE, document)

        document = services.get_policy_document('test-bucketname', readwrite=False)
        self.assertEqual(POLICY_DOCUMENT_READONLY, document)

    @patch('control_panel_api.aws.put_bucket_logging')
    @patch('control_panel_api.aws.create_bucket')
    def test_create_bucket(self, mock_create_bucket, mock_put_bucket_logging):
        services.create_bucket('test-bucketname')

        mock_create_bucket.assert_called_with('test-bucketname', region='eu-test-2', acl='private')
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
            call('arn:aws:iam::1337:policy/test-bucketname-readwrite'),
            call('arn:aws:iam::1337:policy/test-bucketname-readonly')
        ]
        mock_detach_policy_from_entities.assert_has_calls(expected_calls)

        expected_calls = [
            call('arn:aws:iam::1337:policy/test-bucketname-readwrite'),
            call('arn:aws:iam::1337:policy/test-bucketname-readonly')
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


@override_settings(ENV='test', IAM_ARN_BASE='arn:aws:iam::1337')
class NamingTestCase(SimpleTestCase):
    def test_policy_name_has_readwrite(self):
        self.assertEqual('bucketname-readonly', services._policy_name('bucketname', readwrite=False))
        self.assertEqual('bucketname-readwrite', services._policy_name('bucketname', readwrite=True))

    def test_policy_arn(self):
        self.assertEqual('arn:aws:iam::1337:policy/bucketname-readonly',
                         services._policy_arn('bucketname', readwrite=False))
        self.assertEqual('arn:aws:iam::1337:policy/bucketname-readwrite',
                         services._policy_arn('bucketname', readwrite=True))

    def test_bucket_arn(self):
        self.assertEqual('arn:aws:s3:::bucketname', services.bucket_arn('bucketname'))
