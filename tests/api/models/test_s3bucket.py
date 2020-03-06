from unittest.mock import call, patch

from botocore.exceptions import ClientError
from django.conf import settings
from model_mommy import mommy
import pytest

from controlpanel.api.models import S3Bucket, UserS3Bucket


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture
def bucket():
    return S3Bucket.objects.create(name="test-bucket-1")


def test_delete_revokes_permissions(bucket, aws):
    users3bucket = mommy.make('api.UserS3Bucket', s3bucket=bucket)
    apps3bucket = mommy.make('api.AppS3Bucket', s3bucket=bucket)

    bucket.delete()

    aws.revoke_bucket_access.assert_has_calls([
        call(apps3bucket.iam_role_name, bucket.arn),
        call(users3bucket.iam_role_name, bucket.arn),
    ])


def test_delete_marks_bucket_for_archival(bucket, aws):
    bucket.delete()
    aws.tag_bucket.assert_called_once_with(bucket.name, {"to-archive": "true"})


def test_delete_marks_bucket_for_archival_when_tag_bucket_fails(bucket, aws):
    aws.tag_bucket.side_effect = ClientError({"error": "true"}, "TagFailed")
    with pytest.raises(ClientError):
        bucket.delete()

    # The S3 bucket record is not deleted from the DB
    assert S3Bucket.objects.filter(name=bucket.name).exists()


def test_bucket_create(aws):
    bucket = S3Bucket.objects.create(name="test-bucket-1")
    aws.create_bucket.assert_called_with(bucket.name, False)


def test_create_users3bucket(aws, superuser):
    bucket = S3Bucket.objects.create(
        name="test-bucket-1",
        created_by=superuser,
    )

    aws.create_bucket.assert_called()

    assert UserS3Bucket.objects.get(user=superuser, s3bucket=bucket)
