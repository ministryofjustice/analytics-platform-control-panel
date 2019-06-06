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


def test_arn(bucket):
    assert 'arn:aws:s3:::test-bucket-1' == bucket.arn


def test_delete_revokes_permissions(bucket, aws):
    users3bucket = mommy.make('api.UserS3Bucket', s3bucket=bucket)
    apps3bucket = mommy.make('api.AppS3Bucket', s3bucket=bucket)

    bucket.delete()

    # expected_calls = (
        # call(bucket.arn, users3bucket.aws_role_name()),
        # call(bucket.arn, apps3bucket.aws_role_name()),
    # )
    # aws.put_role_policy.assert_has_calls(expected_calls, any_order=True)
    aws.put_role_policy.assert_called()
    # TODO assert calls remove bucket ARN


def test_bucket_create(aws):
    url = 'http://foo.com/'

    aws.create_bucket.return_value = {'Location': url}

    bucket = S3Bucket.objects.create(name="test-bucket-1")

    aws.create_bucket.assert_called_with(
        bucket.name,
        region=settings.BUCKET_REGION,
        acl='private',
    )

    assert url == bucket.location_url


def test_create_users3bucket(aws, superuser):
    bucket = S3Bucket.objects.create(
        name="test-bucket-1",
        created_by=superuser,
    )

    aws.create_bucket.assert_called()

    assert UserS3Bucket.objects.get(user=superuser, s3bucket=bucket)
