import json

from unittest.case import TestCase
from unittest.mock import MagicMock, call, patch

from control_panel_api.aws import aws


@patch.object(aws, 'client', MagicMock())
class AwsTestCase(TestCase):

    def test_create_bucket(self):
        aws.create_bucket('bucketname', 'eu-west-1')
        aws.client.return_value.create_bucket.assert_called()

    def test_put_bucket_logging(self):
        aws.put_bucket_logging('bucketname', 'target_bucket', 'target_prefix')
        aws.client.return_value.put_bucket_logging.assert_called()

    def test_create_policy_json_encoded(self):
        aws.create_policy('bucketname', {'foo': 'bar'})
        aws.client.return_value.create_policy.assert_called_with(
            PolicyName='bucketname',
            PolicyDocument='{"foo": "bar"}'
        )

    def test_delete_policy(self):
        aws.delete_policy('policyarn')
        aws.client.return_value.delete_policy.assert_called()

    def test_detach_policy_from_entities(self):
        aws.client.return_value.list_entities_for_policy.return_value = {
            'PolicyRoles': [{'RoleName': 'foo'}],
            'PolicyGroups': [{'GroupName': 'bar'}],
            'PolicyUsers': [{'UserName': 'baz'}],
        }

        aws.detach_policy_from_entities('policyarn')

        aws.client.return_value.list_entities_for_policy.assert_called()
        aws.client.return_value.detach_role_policy.assert_called_with(
            RoleName='foo',
            PolicyArn='policyarn',
        )
        aws.client.return_value.detach_group_policy.assert_called_with(
            GroupName='bar',
            PolicyArn='policyarn',
        )
        aws.client.return_value.detach_user_policy.assert_called_with(
            UserName='baz',
            PolicyArn='policyarn',
        )

    def test_attach_policy_to_role(self):
        aws.attach_policy_to_role('policyarn', 'rolename')
        aws.client.return_value.attach_role_policy.assert_called_with(
            RoleName='rolename',
            PolicyArn='policyarn',
        )

    def test_detach_policy_from_role(self):
        aws.detach_policy_from_role('policyarn', 'foo')
        aws.client.return_value.detach_role_policy.assert_called()

    def test_detach_policy_from_group(self):
        aws.detach_policy_from_group('policyarn', 'foo')
        aws.client.return_value.detach_group_policy.assert_called()

    def test_detach_policy_from_user(self):
        aws.detach_policy_from_user('policyarn', 'foo')
        aws.client.return_value.detach_user_policy.assert_called()

    def test_create_role(self):
        role_name = "a_role"
        assume_role_policy = {"test policy": True}

        aws.create_role(role_name, assume_role_policy)

        aws.client.return_value.create_role.assert_called_with(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
        )

    def test_delete_role(self):
        aws.client.return_value.list_attached_role_policies.return_value = {
            "AttachedPolicies": [
                {"PolicyArn": "arn_1"},
                {"PolicyArn": "arn_2"},
            ],
        }

        role_name = "a_role"
        aws.delete_role(role_name)

        expected_detach_calls = [
            call(RoleName=role_name, PolicyArn='arn_1'),
            call(RoleName=role_name, PolicyArn='arn_2'),
        ]

        # Check policies are detached from role
        aws.client.return_value.detach_role_policy.assert_has_calls(
            expected_detach_calls)

        # Check role is deleted
        aws.client.return_value.delete_role.assert_called_with(
            RoleName=role_name,
        )
