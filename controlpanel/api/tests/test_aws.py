import json
from unittest.case import TestCase
from unittest.mock import MagicMock, call, patch

from botocore.exceptions import ClientError

from control_panel_api.aws import aws


@patch.object(aws, 'client', MagicMock())
class AwsTestCase(TestCase):

    def test_create_bucket(self):
        aws.create_bucket('bucketname', 'eu-west-1')
        aws.client.return_value.create_bucket.assert_called()

    def test_put_bucket_logging(self):
        aws.put_bucket_logging('bucketname', 'target_bucket', 'target_prefix')
        aws.client.return_value.put_bucket_logging.assert_called()

    def test_get_inline_policy_document_when_found(self):
        role_name = 'test-user-rolename'
        policy_name = 's3-access'
        policy_document = {'test': 'policy document'}

        aws.client.return_value.get_role_policy.return_value = {
            'PolicyDocument': policy_document,
        }

        document = aws.get_inline_policy_document(role_name, policy_name)
        self.assertEqual(document, policy_document)

    def test_get_inline_policy_document_when_not_found(self):
        role_name = 'test-user-rolename'
        policy_name = 's3-access'

        not_found_error = ClientError({'Error': {'Code': 'NoSuchEntity'}}, 'get_role_policy')
        aws.client.return_value.get_role_policy.side_effect = not_found_error

        document = aws.get_inline_policy_document(role_name, policy_name)
        self.assertEqual(document, None)

    @patch.object(aws, 'enabled', False)
    def test_get_inline_policy_document_when_not_writing_to_cluster(self):
        document = aws.get_inline_policy_document('test-user-role', 's3-access')
        self.assertEqual(document, None)

    def test_put_role_policy(self):
        role_name = 'test-user-rolename'
        policy_name = 's3-access'
        policy_document = {'test': 'policy document'}

        aws.put_role_policy(role_name, policy_name, policy_document)
        aws.client.return_value.put_role_policy.assert_called_with(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
        )

    def test_attach_policy_to_role(self):
        aws.attach_policy_to_role('policyarn', 'rolename')
        aws.client.return_value.attach_role_policy.assert_called_with(
            RoleName='rolename',
            PolicyArn='policyarn',
        )

    def test_detach_policy_from_role(self):
        aws.detach_policy_from_role('policy_arn', 'role_name')
        aws.client.return_value.detach_role_policy.assert_called_with(
            RoleName='role_name',
            PolicyArn='policy_arn',
        )

    def test_delete_role_inline_policy(self):
        aws.delete_role_inline_policy('policy_name', 'role_name')
        aws.client.return_value.delete_role_policy.assert_called_with(
            RoleName='role_name',
            PolicyName='policy_name',
        )

    def test_create_role(self):
        role_name = "a_role"
        assume_role_policy = {"test policy": True}

        aws.create_role(role_name, assume_role_policy)

        aws.client.return_value.create_role.assert_called_with(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
        )

    def test_delete_role(self):
        aws_client = aws.client.return_value
        aws_client.list_attached_role_policies.return_value = {
            "AttachedPolicies": [
                {"PolicyArn": "arn_1"},
                {"PolicyArn": "arn_2"},
            ],
        }
        aws_client.list_role_policies.return_value = {
            "PolicyNames": [
                's3-access',
                'other-inline-policy',
            ],
        }

        role_name = "a_role"
        aws.delete_role(role_name)

        # Check managed policies are detached from role
        expected_detach_calls = [
            call(RoleName=role_name, PolicyArn='arn_1'),
            call(RoleName=role_name, PolicyArn='arn_2'),
        ]
        aws_client.detach_role_policy.assert_has_calls(
            expected_detach_calls)

        # Check inline policies are deleted
        expected_delete_policy_calls = [
            call(RoleName=role_name, PolicyName='s3-access'),
            call(RoleName=role_name, PolicyName='other-inline-policy'),
        ]
        aws_client.delete_role_policy.assert_has_calls(
            expected_delete_policy_calls)

        # Check role is deleted
        aws.client.return_value.delete_role.assert_called_with(
            RoleName=role_name,
        )
