# Standard library
from unittest.mock import PropertyMock, patch

# Third-party
import pytest
from django.conf import settings
from django.db.utils import IntegrityError
from model_bakery import baker

# First-party/Local
from controlpanel.api.models import UserS3Bucket
from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


@pytest.fixture
def user():
    return baker.make("api.User", auth0_id="github|user_1", username="user_1")


@pytest.fixture
def bucket():
    return baker.make("api.S3Bucket", name="test-bucket-1")


@pytest.fixture
def users3bucket(user, bucket):
    return user.users3buckets.create(
        s3bucket=bucket,
        access_level=AccessToS3Bucket.READONLY,
    )


@pytest.mark.django_db
def test_one_record_per_user_per_s3bucket(user, bucket, users3bucket):
    with pytest.raises(IntegrityError):

        user.users3buckets.create(
            s3bucket=bucket,
            access_level=AccessToS3Bucket.READWRITE,
        )


@pytest.mark.django_db
def test_aws_create_bucket(user, bucket, sqs, helpers):
    users3bucket = user.users3buckets.create(
        s3bucket=bucket,
        access_level=AccessToS3Bucket.READONLY
    )
    messages = helpers.retrieve_messages(sqs, settings.IAM_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        messages, UserS3Bucket.__name__, users3bucket.id, settings.IAM_QUEUE_NAME
    )


@pytest.mark.django_db
@patch("controlpanel.api.models.users3bucket.tasks")
def test_aws_create_folder(tasks, user, bucket):
    with patch.object(
        bucket.__class__, "is_folder", new_callable=PropertyMock(return_value=True)
    ):
        user_bucket = user.users3buckets.create(
            s3bucket=bucket,
            access_level=AccessToS3Bucket.READONLY,
            current_user=user
        )
        tasks.S3BucketGrantToUser.assert_called_once_with(
            user_bucket, user
        )
        tasks.S3BucketGrantToUser.return_value.create_task.assert_called_once()


@pytest.mark.django_db
def test_delete_revoke_permissions(bucket, users3bucket):
    with patch(
        "controlpanel.api.tasks.S3BucketRevokeUserAccess"
    ) as revoke_user_access_task:
        users3bucket.delete()
        revoke_user_access_task.assert_called_once_with(users3bucket, None)
        revoke_user_access_task.return_value.create_task.assert_called_once()
