import json
from unittest.mock import patch, call

from django.test.testcases import SimpleTestCase, override_settings

from control_panel_api import services


@override_settings(ENV='test', BUCKET_REGION='eu-test-2', LOGS_BUCKET_NAME='moj-test-logs',
                   IAM_ARN_BASE='arn:aws:iam::1337')
class ServicesTestCase(SimpleTestCase):
    def test_policy_document_readwrite(self):
        document = services.get_policy_document('foo', readwrite=True)

        sids = [s['Sid'] for s in document['Statement']]
        self.assertIn('UpdateRenameAndDeleteObjects', sids)

        document = services.get_policy_document('foo', readwrite=False)

        sids = [s['Sid'] for s in document['Statement']]
        self.assertNotIn('UpdateRenameAndDeleteObjects', sids)

    @patch('control_panel_api.aws.put_bucket_logging')
    @patch('control_panel_api.aws.create_bucket')
    def test_create_bucket(self, mock_create_bucket, mock_put_bucket_logging):
        services.create_bucket('bucketname')

        mock_create_bucket.assert_called_with('test-bucketname', region='eu-test-2', acl='private')
        mock_put_bucket_logging.assert_called_with('test-bucketname', target_bucket='moj-test-logs',
                                                   target_prefix='test-bucketname/')

    @patch('control_panel_api.aws.create_policy')
    def test_create_bucket_policies(self, mock_create_policy):
        services.create_bucket_policies('bucketname')

        expected_calls = [
            call('test-bucketname-readwrite', services.get_policy_document('test-bucketname', True)),
            call('test-bucketname-readonly', services.get_policy_document('test-bucketname', False)),
        ]
        mock_create_policy.assert_has_calls(expected_calls)

    @patch('control_panel_api.aws.delete_policy')
    @patch('control_panel_api.aws.detach_policy_from_entities')
    def test_delete_bucket_policies(self, mock_detach_policy_from_entities, mock_delete_policy):
        services.delete_bucket_policies('bucketname')

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
        services.bucket_create('bucketname')

        mock_create_bucket_policies.assert_called()
        mock_create_bucket.assert_called()

    @patch('control_panel_api.services.delete_bucket_policies')
    def test_bucket_create(self, mock_delete_bucket_policies):
        services.bucket_delete('bucketname')

        mock_delete_bucket_policies.assert_called()


@override_settings(ENV='test', IAM_ARN_BASE='arn:aws:iam::1337')
class NamingTestCase(SimpleTestCase):
    def test_bucket_name_has_env(self):
        self.assertEqual('test-bucketname', services._bucket_name('bucketname'))

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
