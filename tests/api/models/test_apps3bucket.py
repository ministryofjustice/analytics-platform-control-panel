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
def grant_bucket_access():
    with patch('controlpanel.api.services.grant_bucket_access') as p:
        yield p


@pytest.yield_fixture
def revoke_bucket_access():
    with patch('controlpanel.api.services.revoke_bucket_access') as p:
        yield p


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
def test_update_aws_permissions(app, bucket, grant_bucket_access):
    apps3bucket = AppS3Bucket(
        app=app,
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )

    apps3bucket.aws_update()

    grant_bucket_access.assert_called_with(
        bucket.arn,
        apps3bucket.has_readwrite_access(),
        app.iam_role_name,
    )


@pytest.mark.django_db
def test_aws_create(app, bucket, grant_bucket_access):
    apps3bucket = AppS3Bucket(
        app=app,
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )

    apps3bucket.aws_create()

    grant_bucket_access.assert_called_with(
        bucket.arn,
        apps3bucket.has_readwrite_access(),
        app.iam_role_name
    )


@pytest.mark.django_db
def test_delete_revoke_permissions(app, bucket, revoke_bucket_access):
    apps3bucket = mommy.make(
        'api.AppS3Bucket',
        app=app,
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )

    apps3bucket.delete()

    revoke_bucket_access.assert_called_with(
        bucket.arn,
        app.iam_role_name,
    )
