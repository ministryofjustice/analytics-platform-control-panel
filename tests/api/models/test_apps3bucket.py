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

    aws.grant_bucket_access.assert_called_with(
        app.iam_role_name,
        bucket.arn,
        AppS3Bucket.READONLY,
        apps3bucket.resources,
    )
    # TODO get policy from call and assert ARN in correct place


@pytest.mark.django_db
def test_aws_create(app, bucket, aws):
    apps3bucket = AppS3Bucket(
        app=app,
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )

    apps3bucket.save()

    aws.grant_bucket_access.assert_called_with(
        app.iam_role_name,
        bucket.arn,
        AppS3Bucket.READONLY,
        apps3bucket.resources,
    )
    # TODO make this test a case on previous


@pytest.mark.django_db
def test_delete_revoke_permissions(app, aws, bucket):
    apps3bucket = mommy.make(
        'api.AppS3Bucket',
        app=app,
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )

    apps3bucket.delete()

    aws.revoke_bucket_access.assert_called_with(
        apps3bucket.iam_role_name,
        bucket.arn,
    )
