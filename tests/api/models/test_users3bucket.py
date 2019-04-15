from unittest.mock import patch

from django.db.utils import IntegrityError
from model_mommy import mommy
import pytest

from controlpanel.api.models import AppS3Bucket


@pytest.fixture
def user():
    return mommy.make('api.User', auth0_id='github|user_1', username="user_1")


@pytest.fixture
def bucket():
    return mommy.make('api.S3Bucket', name="test-bucket-1")


@pytest.fixture
def users3bucket(user, bucket):
    return user.users3buckets.create(
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )


@pytest.mark.django_db
def test_one_record_per_user_per_s3bucket(user, bucket, users3bucket):
    with pytest.raises(IntegrityError):

        user.users3buckets.create(
            s3bucket=bucket,
            access_level=users3bucket.READWRITE,
        )


@pytest.mark.django_db
def test_aws_create(user, bucket, users3bucket):
    with patch('controlpanel.api.services.grant_bucket_access') as grant:

        users3bucket.aws_create()

        grant.assert_called_with(
            bucket.arn,
            users3bucket.has_readwrite_access(),
            user.iam_role_name,
        )


@pytest.mark.django_db
def test_delete_revoke_permissions(user, bucket, users3bucket):
    with patch('controlpanel.api.services.revoke_bucket_access') as revoke:

        users3bucket.delete()

        revoke.assert_called_with(bucket.arn, user.iam_role_name)
