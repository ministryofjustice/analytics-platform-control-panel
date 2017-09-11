import json
from unittest.mock import patch, call

from django.test.testcases import SimpleTestCase, override_settings

from control_panel_api import services


@override_settings(ENV='test', BUCKET_REGION='eu-test-2', LOGS_BUCKET_NAME='moj-test-logs')
class ServicesTestCase(SimpleTestCase):
    def test_policy_document_readwrite(self):
        document = services.get_policy_document('foo', readwrite=True)

        sids = [s['Sid'] for s in document['Statement']]
        self.assertIn('UpdateRenameAndDeleteObjects', sids)

        document = services.get_policy_document('foo', readwrite=False)

        sids = [s['Sid'] for s in document['Statement']]
        self.assertNotIn('UpdateRenameAndDeleteObjects', sids)

    @patch('boto3.client')
    def test_create_bucket(self, mock_client):
        services.create_bucket('bucketname')

        mock_client.return_value.create_bucket.assert_called_with(
            Bucket='test-bucketname',
            ACL='private',
            CreateBucketConfiguration={
                'LocationConstraint': 'eu-test-2',
            },
        )
        mock_client.return_value.put_bucket_logging.assert_called_with(
            Bucket='test-bucketname',
            BucketLoggingStatus={
                'LoggingEnabled': {
                    'TargetBucket': 'moj-test-logs',
                    'TargetPrefix': 'test-bucketname/'
                }
            }
        )

    @patch('boto3.client')
    def test_delete_bucket(self, mock_client):
        services.delete_bucket('bucketname')

        mock_client.return_value.delete_bucket.assert_called_with(
            Bucket='test-bucketname',
        )

    @patch('boto3.client')
    def test_create_bucket_policies(self, mock_client):
        services.create_bucket_policies('bucketname')

        expected_calls = [
            call(
                PolicyName='test-bucketname-readwrite',
                PolicyDocument=json.dumps(services.get_policy_document('test-bucketname', True))
            ),
            call(
                PolicyName='test-bucketname-readonly',
                PolicyDocument=json.dumps(services.get_policy_document('test-bucketname', False))
            )
        ]
        mock_client.return_value.create_policy.assert_has_calls(expected_calls)


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
        self.assertEqual('arn:aws:s3:::bucketname', services._bucket_arn('bucketname'))
