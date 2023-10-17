# Standard library
from unittest.mock import MagicMock, patch

# Third-party
import pytest
from model_mommy import mommy

# First-party/Local
from controlpanel.api.models import AppS3Bucket, S3Bucket, UserS3Bucket
from controlpanel.api.tasks.handlers import (
    create_s3bucket,
    grant_app_s3bucket_access,
    grant_user_s3bucket_access,
    revoke_all_access_s3bucket,
    revoke_app_s3bucket_access,
    revoke_user_s3bucket_access,
)


@pytest.mark.django_db
@pytest.mark.parametrize("task_method, model", [
    (create_s3bucket, S3Bucket),
    (grant_app_s3bucket_access, AppS3Bucket),
    (grant_user_s3bucket_access, UserS3Bucket),
])
@patch("controlpanel.api.tasks.handlers.base.BaseTaskHandler.complete")
def test_exception_raised_when_called_without_valid_app(
    complete, users, task_method, model
):
    with pytest.raises(model.DoesNotExist):
        task_method(1, users["superuser"].pk)

        complete.assert_not_called()


@pytest.mark.django_db
@patch("controlpanel.api.tasks.handlers.base.BaseTaskHandler.complete")
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
@patch("controlpanel.api.tasks.handlers.base.BaseTaskHandler.complete")
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


@pytest.mark.django_db
@pytest.mark.parametrize("bucket_name, is_folder", [
    ("example-bucket", False),
    ("example-bucket/folder", True),
])
@patch("controlpanel.api.tasks.handlers.base.BaseTaskHandler.complete")
@patch("controlpanel.api.tasks.handlers.s3.cluster")
def test_revoke_user_access(cluster, complete, bucket_name, is_folder):
    user_bucket_access = mommy.make("api.UserS3Bucket", s3bucket__name=bucket_name)
    s3bucket = user_bucket_access.s3bucket
    bucket_identifier = s3bucket.name if is_folder else s3bucket.arn
    revoke_user_s3bucket_access(
        bucket_identifier=bucket_identifier,
        bucket_user_pk=user_bucket_access.user.pk,
        is_folder=is_folder
    )

    cluster.User.assert_called_once_with(user_bucket_access.user)
    if is_folder:
        cluster.User.return_value.revoke_folder_access.assert_called_once_with(
            bucket_identifier
        )
    else:
        cluster.User.return_value.revoke_bucket_access.assert_called_once_with(
            bucket_identifier
        )

    complete.assert_called_once()


@pytest.mark.django_db
@patch("controlpanel.api.tasks.handlers.base.BaseTaskHandler.complete")
@patch("controlpanel.api.tasks.handlers.s3.cluster")
def test_revoke_app_access(cluster, complete):
    app_bucket_access = mommy.make("api.AppS3Bucket")
    revoke_app_s3bucket_access(
        bucket_arn=app_bucket_access.s3bucket.arn,
        app_pk=app_bucket_access.app.pk,
    )

    cluster.App.assert_called_once_with(app_bucket_access.app)
    cluster.App.return_value.revoke_bucket_access.assert_called_once_with(
        app_bucket_access.s3bucket.arn
    )
    complete.assert_called_once()


@pytest.mark.django_db
@patch("controlpanel.api.models.UserS3Bucket.revoke_bucket_access", new=MagicMock())
@patch("controlpanel.api.models.AppS3Bucket.revoke_bucket_access", new=MagicMock())
@patch("controlpanel.api.models.PolicyS3Bucket.revoke_bucket_access", new=MagicMock())
def test_revoke_all_access(users):
    bucket = mommy.make("api.S3Bucket")
    user_access = mommy.make("api.UserS3Bucket", s3bucket=bucket)
    app_access = mommy.make("api.AppS3Bucket", s3bucket=bucket)
    policy_access = mommy.make("api.PolicyS3Bucket", s3bucket=bucket)
    task = mommy.make("api.Task", user_id=users["superuser"].pk)

    revoke_all_access_s3bucket(bucket.pk, task.user_id)

    user_access.revoke_bucket_access.assert_called_once_with(
        revoked_by=users["superuser"],
    )
    app_access.revoke_bucket_access.assert_called_once_with(
        revoked_by=users["superuser"],
    )
    policy_access.revoke_bucket_access.assert_called_once_with(
        revoked_by=users["superuser"],
    )
