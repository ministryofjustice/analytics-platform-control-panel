from unittest.mock import call, patch

from model_mommy import mommy
import pytest

from controlpanel.api.models import S3Bucket


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture
def bucket():
    return S3Bucket.objects.create(name="test-bucket-1")


def test_arn(bucket):
    assert 'arn:aws:s3:::test-bucket-1' == bucket.arn


def test_delete_revokes_permissions(bucket):
    users3bucket = mommy.make('api.UserS3Bucket', s3bucket=bucket)
    apps3bucket = mommy.make('api.AppS3Bucket', s3bucket=bucket)

    with patch('controlpanel.api.services.revoke_bucket_access') as revoke:
        bucket.delete()

        expected_calls = (
            call(bucket.arn, users3bucket.aws_role_name()),
            call(bucket.arn, apps3bucket.aws_role_name()),
        )
        revoke.assert_has_calls(expected_calls, any_order=True)


def test_bucket_create(bucket):
    url = 'http://foo.com/'

    with patch('controlpanel.api.services.create_bucket') as create:
        create.return_value = {'Location': url}

        bucket.aws_create()

        create.assert_called_with(
            bucket.name,
            bucket.is_data_warehouse,
        )

    assert url == bucket.location_url


def test_create_users3bucket(bucket):
    with patch('controlpanel.api.models.UserS3Bucket.aws_create') as aws_create:

        bucket.create_users3bucket(mommy.make('api.User'))

        aws_create.assert_called()
