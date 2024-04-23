# Standard library
from unittest.mock import call, patch

# Third-party
import pytest
from botocore.exceptions import ClientError
from django.conf import settings
from model_bakery import baker

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import S3Bucket, UserS3Bucket


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture
def bucket():
    return S3Bucket.objects.create(name="test-bucket-1")


def test_delete_revokes_permissions(bucket):
    with (
        patch(
            "controlpanel.api.models.AppS3Bucket.revoke_bucket_access"
        ) as app_revoke_bucket_access,
        patch(
            "controlpanel.api.models.UserS3Bucket.revoke_bucket_access"
        ) as user_revoke_user_bucket_access,
    ):
        # link the bucket with an UserS3Bucket and AppS3Bucket
        baker.make("api.UserS3Bucket", s3bucket=bucket)
        baker.make("api.AppS3Bucket", s3bucket=bucket)
        # delete the source S3Bucket
        bucket.delete()
        # check that related objects revoke access methods were called
        app_revoke_bucket_access.assert_called_once()
        user_revoke_user_bucket_access.assert_called_once()


def test_delete_marks_bucket_for_archival(bucket):
    with patch("controlpanel.api.cluster.AWSBucket.tag_bucket") as tag_bucket:
        bucket.delete()
        tag_bucket.assert_called_once_with(bucket.name, {"to-archive": "true"})


def test_delete_marks_bucket_for_archival_when_tag_bucket_fails(bucket):
    with patch("controlpanel.api.cluster.AWSBucket.tag_bucket") as tag_bucket:
        tag_bucket.side_effect = ClientError({"error": "true"}, "TagFailed")
        with pytest.raises(ClientError):
            bucket.delete()

        # The S3 bucket record is not deleted from the DB
        assert S3Bucket.objects.filter(name=bucket.name).exists()


def test_bucket_create(sqs, superuser, helpers):
    bucket = S3Bucket.objects.create(name="test-bucket-1")
    messages = helpers.retrieve_messages(sqs, queue_name=settings.S3_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        messages,
        S3Bucket.__name__,
        bucket.id,
        queue_name=settings.S3_QUEUE_NAME,
    )


def test_create_users3bucket(sqs, superuser, helpers):
    bucket = S3Bucket.objects.create(
        name="test-bucket-1",
        created_by=superuser,
    )
    user_s3bucket = UserS3Bucket.objects.get(user=superuser, s3bucket=bucket)
    assert user_s3bucket
    s3_messages = helpers.retrieve_messages(sqs, queue_name=settings.S3_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        s3_messages, S3Bucket.__name__, bucket.id, queue_name=settings.S3_QUEUE_NAME
    )
    iam_messages = helpers.retrieve_messages(sqs, queue_name=settings.IAM_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        iam_messages, UserS3Bucket.__name__, user_s3bucket.id, queue_name=settings.IAM_QUEUE_NAME
    )


@pytest.mark.parametrize(
    "name,expected",
    [
        ("bucketname/foldername", True),
        ("bucketname", False),
    ],
)
def test_is_folder(name, expected):
    assert S3Bucket(name=name).is_folder is expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("bucketname/foldername", cluster.S3Folder),
        ("bucketname", cluster.S3Bucket),
    ],
)
def test_cluster(name, expected):
    assert isinstance(S3Bucket(name=name).cluster, expected)


def test_soft_delete_bucket(bucket, users, sqs, helpers):
    user = users["superuser"]

    assert bucket.is_deleted is False
    with patch("controlpanel.api.cluster.S3Bucket.mark_for_archival") as archive:
        bucket.soft_delete(deleted_by=user)

    assert bucket.is_deleted is True
    assert bucket.deleted_by == user
    assert bucket.deleted_at is not None
    archive.assert_called_once()

    messages = helpers.retrieve_messages(sqs, queue_name=settings.S3_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        messages,
        S3Bucket.__name__,
        bucket.id,
        queue_name=settings.S3_QUEUE_NAME,
    )


def test_soft_delete_folder(users, sqs, helpers):
    folder = S3Bucket.objects.create(name="bucket/folder-1")
    user = users["superuser"]

    assert folder.is_deleted is False
    folder.soft_delete(deleted_by=user)

    assert folder.is_deleted is True
    assert folder.deleted_by == user
    assert folder.deleted_at is not None

    messages = helpers.retrieve_messages(sqs, queue_name=settings.S3_QUEUE_NAME)
    task_names = [message["headers"]["task"] for message in messages]

    helpers.validate_task_with_sqs_messages(
        messages,
        S3Bucket.__name__,
        folder.id,
        queue_name=settings.S3_QUEUE_NAME,
    )
    assert "archive_s3bucket" in task_names
    assert "s3bucket_revoke_all_access" in task_names
