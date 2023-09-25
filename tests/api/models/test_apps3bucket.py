# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.conf import settings
from django.db.utils import IntegrityError
from model_mommy import mommy

# First-party/Local
from controlpanel.api.models import AppS3Bucket


@pytest.fixture
def app():
    return mommy.make("api.App", name="app_1")


@pytest.fixture
def bucket():
    return mommy.make("api.S3Bucket", name="test-bucket-1")


@pytest.mark.django_db
def test_one_record_per_app_per_s3bucket(app, bucket):
    # Give app access to bucket (read-only)
    with patch("controlpanel.api.aws.AWSRole.grant_bucket_access"):
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
def test_aws_permissions(app, bucket, sqs, helpers):
    apps3bucket = AppS3Bucket(
        app=app,
        s3bucket=bucket,
        access_level=AppS3Bucket.READONLY,
    )

    apps3bucket.save()
    messages = helpers.retrieve_messages(sqs, queue_name=settings.IAM_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        messages, AppS3Bucket.__name__, apps3bucket.id, settings.IAM_QUEUE_NAME
    )


@pytest.mark.django_db
def test_delete_revoke_permissions(app, bucket):
    with patch(
        "controlpanel.api.tasks.S3BucketRevokeAppAccess"
    ) as revoke_bucket_access_task:
        apps3bucket = mommy.make(
            "api.AppS3Bucket",
            app=app,
            s3bucket=bucket,
            access_level=AppS3Bucket.READONLY,
        )

        apps3bucket.delete()

        revoke_bucket_access_task.assert_called_once_with(
            apps3bucket,
            None
        )
        revoke_bucket_access_task.return_value.create_task.assert_called_once()
