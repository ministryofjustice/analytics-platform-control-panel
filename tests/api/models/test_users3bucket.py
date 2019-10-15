from unittest.mock import patch

from django.db.utils import IntegrityError
from model_mommy import mommy
import pytest

from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


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
def test_aws_create(user, bucket, aws):

    user.users3buckets.create(
        s3bucket=bucket,
        access_level=AccessToS3Bucket.READONLY,
    )

    aws.grant_bucket_access.assert_called_with(
        user.iam_role_name,
        bucket.arn,
        AccessToS3Bucket.READONLY,
    )
    # TODO get policy from call and assert bucket ARN present


@pytest.mark.django_db
def test_delete_revoke_permissions(user, bucket, users3bucket, aws):
    users3bucket.delete()

    aws.revoke_bucket_access.assert_called_with(
        user.iam_role_name,
        bucket.arn,
    )
    # TODO get policy from call and assert bucket ARN removed
