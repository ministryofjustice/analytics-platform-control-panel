# Standard library
from unittest.mock import MagicMock, PropertyMock, call, patch

# Third-party
from django.core.management import call_command


@patch("controlpanel.cli.management.commands.feedback_csv.AWSBucket")
def test_feedback_csv_no_feedback(mock_bucket, db):
    call_command("feedback_csv", "--num_weeks", "2")

    # Assert that with no feedback present, the following methods aren't called
    mock_bucket.return_value.exists.assert_not_called()
    mock_bucket.return_value.create.assert_not_called()
    mock_bucket.return_value.write_to_bucket.assert_not_called()


@patch("controlpanel.cli.management.commands.feedback_csv.AWSBucket")
def test_feedback_csv_no_bucket(mock_bucket, db, feedback):
    mock_bucket.return_value.exists.return_value = False
    call_command("feedback_csv", "--num_weeks", "2")

    # Assert that with feedback present, the following methods aren't called
    mock_bucket.return_value.exists.assert_called_with("test-feedback-bucket")
    mock_bucket.return_value.create.assert_called_with("test-feedback-bucket")
    mock_bucket.return_value.write_to_bucket.assert_called_once()


@patch("controlpanel.cli.management.commands.feedback_csv.AWSBucket")
def test_feedback_csv_bucket_exists(mock_bucket, db, feedback):
    mock_bucket.return_value.exists.return_value = True
    call_command("feedback_csv", "--num_weeks", "2")

    # Assert that with feedback present, the following methods aren't called
    mock_bucket.return_value.exists.assert_called_with("test-feedback-bucket")
    mock_bucket.return_value.create.assert_not_called()
    mock_bucket.return_value.write_to_bucket.assert_called_once()
