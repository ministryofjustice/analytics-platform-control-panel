from unittest.mock import patch

from django.db.utils import IntegrityError
from model_mommy import mommy
import pytest

from controlpanel.api.models import AppS3Bucket


@pytest.fixture
def app():
    return mommy.make('api.App', name="app_1")


@pytest.fixture
def bucket():
    return mommy.make('api.S3Bucket', name="test-bucket-1")


@pytest.yield_fixture
def revoke_bucket_access():
    with patch('controlpanel.api.services.revoke_bucket_access') as p:
        yield p


@pytest.yield_fixture
def s3_access_policy():
    with patch('controlpanel.api.models.access_to_s3bucket.S3AccessPolicy') as S3AccessPolicy:
        yield S3AccessPolicy


@pytest.mark.django_db
def test_one_record_per_app_per_s3bucket(app, bucket):
    # Give app access to bucket (read-only)
    app.apps3buckets.create(
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )

    with pytest.raises(IntegrityError):
        app.apps3buckets.create(
            s3bucket=bucket,
            access_level=AppS3Bucket.READWRITE,
        )


@pytest.mark.django_db
def test_update_aws_permissions(app, bucket, aws):
    apps3bucket = AppS3Bucket(
        app=app,
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )

    apps3bucket.save()

    aws.put_role_policy.assert_called()
    # TODO get policy from call and assert ARN in correct place


@pytest.mark.django_db
def test_aws_create(app, bucket, aws):
    apps3bucket = AppS3Bucket(
        app=app,
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )

    apps3bucket.save()

    aws.put_role_policy.assert_called()
    # TODO make this test a case on previous


@pytest.mark.django_db
def test_delete_revoke_permissions(app, bucket, s3_access_policy):
    apps3bucket = mommy.make(
        'api.AppS3Bucket',
        app=app,
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )

    apps3bucket.delete()

    s3_access_policy.load.assert_called_with(apps3bucket.aws_role_name())
    policy = s3_access_policy.load.return_value.__enter__.return_value
    policy.revoke_access.assert_called_with(bucket.arn)
