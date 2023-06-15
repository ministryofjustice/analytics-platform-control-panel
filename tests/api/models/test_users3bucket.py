# Standard library
from unittest.mock import patch, PropertyMock

# Third-party
import pytest
from django.db.utils import IntegrityError
from model_mommy import mommy

# First-party/Local
from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


@pytest.fixture
def user():
    return mommy.make("api.User", auth0_id="github|user_1", username="user_1")


@pytest.fixture
def bucket():
    return mommy.make("api.S3Bucket", name="test-bucket-1")


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
def test_aws_create_bucket(user, bucket):
    with patch(
        "controlpanel.api.cluster.AWSRole.grant_bucket_access"
    ) as grant_bucket_access:
        users3bucket = user.users3buckets.create(
            s3bucket=bucket,
            access_level=AccessToS3Bucket.READONLY,
        )

        grant_bucket_access.assert_called_with(
            user.iam_role_name,
            bucket.arn,
            AccessToS3Bucket.READONLY,
            users3bucket.resources,
        )
        # TODO get policy from call and assert bucket ARN present


@pytest.mark.django_db
@patch("controlpanel.api.cluster.AWSRole.grant_folder_access")
def test_aws_create_folder(grant_folder_access, user, bucket):
    with patch.object(
        bucket.__class__, "is_folder", new_callable=PropertyMock(return_value=True)
    ):
        user.users3buckets.create(
            s3bucket=bucket,
            access_level=AccessToS3Bucket.READONLY,
        )
        grant_folder_access.assert_called_with(
            role_name=user.iam_role_name,
            bucket_arn=bucket.arn,
            access_level=AccessToS3Bucket.READONLY,
            paths=[bucket.arn],
        )


@pytest.mark.django_db
def test_delete_revoke_permissions(user, bucket, users3bucket):
    with patch(
        "controlpanel.api.cluster.AWSRole.revoke_bucket_access"
    ) as revoke_bucket_access_action:
        users3bucket.delete()
        revoke_bucket_access_action.assert_called_with(
            user.iam_role_name,
            bucket.arn,
        )
        # TODO get policy from call and assert bucket ARN removed
