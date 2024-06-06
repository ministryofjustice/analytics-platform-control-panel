# Standard library
from unittest.mock import MagicMock, PropertyMock, call, patch

# Third-party
import pytest
from django.core.management import call_command


@pytest.fixture
def quicksight():
    yield MagicMock()


@pytest.fixture(autouse=True)
def mock_boto(quicksight):
    with patch(
        "controlpanel.api.aws.AWSQuicksight.boto3_session", new_callable=PropertyMock
    ) as mock:
        mock.return_value.client.return_value = quicksight
        yield mock


@patch("controlpanel.cli.management.commands.quicksight_delete_users.Command.usernames_from_file")
def test_quicksight_delete_users(usernames_from_file, quicksight):
    quicksight.describe_user.return_value = {"User": {"Role": "READER"}}

    usernames_from_file.return_value = ["user1", "user2", "user3"]

    call_command("quicksight_delete_users", "file.csv", "--delete", "--awsaccountid", "1234567890")

    # Assert that the delete_user method was called for each user
    quicksight.delete_user.assert_has_calls(
        [
            call(UserName="user1", AwsAccountId="1234567890", Namespace="default"),
            call(UserName="user2", AwsAccountId="1234567890", Namespace="default"),
            call(UserName="user3", AwsAccountId="1234567890", Namespace="default"),
        ],
        any_order=True,
    )


@patch("controlpanel.cli.management.commands.quicksight_delete_users.Command.usernames_from_file")
def test_quicksight_doesnt_delete_users(usernames_from_file, quicksight):

    quicksight.describe_user.return_value = {"User": {"Role": "AUTHOR"}}
    usernames_from_file.return_value = ["user1", "user2", "user3"]

    call_command("quicksight_delete_users", "file.csv", "--delete", "--awsaccountid", "1234567890")

    quicksight.delete_user.assert_not_called()


@patch("controlpanel.cli.management.commands.quicksight_delete_users.Command.usernames_from_file")
def test_quicksight_delete_users_dry_run(usernames_from_file, quicksight):
    quicksight.describe_user.return_value = {"User": {"Role": "READER"}}
    usernames_from_file.return_value = ["user1", "user2", "user3"]

    call_command("quicksight_delete_users", "file.csv", "--awsaccountid", "1234567890")

    quicksight.delete_user.assert_not_called()
