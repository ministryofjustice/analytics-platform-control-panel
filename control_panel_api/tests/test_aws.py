from unittest.case import TestCase
from unittest.mock import patch

from control_panel_api import aws


@patch('boto3.client')
class AwsTestCase(TestCase):
    def test_create_bucket(self, mock_client):
        aws.create_bucket('bucketname', 'eu-west-1')
        mock_client.return_value.create_bucket.assert_called()

    def test_put_bucket_logging(self, mock_client):
        aws.put_bucket_logging('bucketname', 'target_bucket', 'target_prefix')
        mock_client.return_value.put_bucket_logging.assert_called()

    def test_create_policy_json_encoded(self, mock_client):
        aws.create_policy('bucketname', {'foo': 'bar'})
        mock_client.return_value.create_policy.assert_called_with(
            PolicyName='bucketname',
            PolicyDocument='{"foo": "bar"}'
        )

    def test_delete_policy(self, mock_client):
        aws.delete_policy('policyarn')
        mock_client.return_value.delete_policy.assert_called()

    def test_detach_policy_from_entities(self, mock_client):
        mock_client.return_value.list_entities_for_policy.return_value = {
            'PolicyRoles': [{'RoleName': 'foo'}],
            'PolicyGroups': [{'GroupName': 'bar'}],
            'PolicyUsers': [{'UserName': 'baz'}],
        }

        aws.detach_policy_from_entities('policyarn')

        mock_client.return_value.list_entities_for_policy.assert_called()
        mock_client.return_value.detach_role_policy.assert_called_with(
            RoleName='foo',
            PolicyArn='policyarn',
        )
        mock_client.return_value.detach_group_policy.assert_called_with(
            GroupName='bar',
            PolicyArn='policyarn',
        )
        mock_client.return_value.detach_user_policy.assert_called_with(
            UserName='baz',
            PolicyArn='policyarn',
        )

    def test_detach_policy_from_role(self, mock_client):
        aws.detach_policy_from_role('policyarn', 'foo')
        mock_client.return_value.detach_role_policy.assert_called()

    def test_detach_policy_from_group(self, mock_client):
        aws.detach_policy_from_group('policyarn', 'foo')
        mock_client.return_value.detach_group_policy.assert_called()

    def test_detach_policy_from_user(self, mock_client):
        aws.detach_policy_from_user('policyarn', 'foo')
        mock_client.return_value.detach_user_policy.assert_called()
