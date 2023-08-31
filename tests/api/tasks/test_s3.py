# Third-party
import pytest
from mock import patch
from model_mommy import mommy

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import AppS3Bucket, S3Bucket, UserS3Bucket
from controlpanel.api.tasks.handlers import (
    create_s3bucket,
    grant_app_s3bucket_access,
    grant_user_s3bucket_access,
)


@pytest.mark.django_db
@pytest.mark.parametrize("task_method, model", [
    (create_s3bucket, S3Bucket),
    (grant_app_s3bucket_access, AppS3Bucket),
    (grant_user_s3bucket_access, UserS3Bucket),
])
@patch("controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.complete")
def test_exception_raised_when_called_without_valid_app(
    complete, users, task_method, model
):
    with pytest.raises(model.DoesNotExist):
        task_method(1, users["superuser"].pk)

        complete.assert_not_called()


@pytest.mark.django_db
@patch("controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.complete")
@patch("controlpanel.api.models.s3bucket.cluster")
def test_bucket_created(cluster, complete, users):
    s3bucket = mommy.make("api.S3Bucket", bucket_owner="APP")

    create_s3bucket(
        s3bucket.pk, users["superuser"].pk, bucket_owner=s3bucket.bucket_owner
    )

    cluster.S3Bucket.assert_called_once_with(s3bucket)
    cluster.S3Bucket.return_value.create.assert_called_once_with(
        owner=s3bucket.bucket_owner
    )
    complete.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize("task_method, model_class, cluster_class", [
    (grant_app_s3bucket_access, "api.AppS3Bucket", "App"),
    (grant_user_s3bucket_access, "api.UserS3Bucket", "User"),
])
@patch("controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.complete")
@patch("controlpanel.api.tasks.handlers.s3.cluster")
def test_access_granted(
    cluster, complete, users, task_method, model_class, cluster_class
):
    obj = mommy.make(model_class)

    task_method(obj.pk, users["superuser"].pk)

    cluster_obj = getattr(cluster, cluster_class)
    cluster_obj.assert_called_once()
    cluster_obj.return_value.grant_bucket_access.assert_called_once()
    complete.assert_called_once()
