from unittest.mock import call, patch

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
        call(apps3bucket.iam_role_name, bucket.arn, apps3bucket.resources),
        call(users3bucket.iam_role_name, bucket.arn, users3bucket.resources),
    ])


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
