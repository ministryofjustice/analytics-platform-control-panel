from celery import shared_task

from controlpanel.api import cluster
from controlpanel.api.models import App, User, S3Bucket, UserS3Bucket, AppS3Bucket


# TODO use acks_late=True, acks_on_failure_or_timeout=False?
# this should mean that for any failure it is will be added back to the queue
# after SQS timeout visibility has passed. Could result in tasks being run forever
# unless SQS defines a limit?
@shared_task(bind=True, max_retries=3)
def create_app_aws_role(self, app_pk):
    try:
        app = App.objects.get(pk=app_pk)
    except App.DoesNotExist as exc:
        # the app does not exist, so add message back to the queue. Is this the best way?
        raise self.retry(exc=exc, countdown=5)

    # this will catch when a role already exists
    cluster.App(app).create_iam_role()


@shared_task(bind=True, max_retries=3)
def create_app_auth_settings(self, app_pk, user_pk, envs, disable_authentication, connections):
    try:
        app = App.objects.get(pk=app_pk)
    except App.DoesNotExist as exc:
        # the app does not exist, so add message back to the queue. Is this the best way?
        raise self.retry(exc=exc, countdown=5)

    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        # user doesnt exist, nothing to do, dont want to retry so return early
        return

    if not user.github_api_token:
        # user doesnt have a githubapi token, log this?
        return

    for env in envs:
        cluster.App(app, user.github_api_token).create_auth_settings(
            env_name=env,
            disable_authentication=disable_authentication,
            connections=connections,
        )


@shared_task(bind=True, max_retries=3)
def create_s3bucket(self, bucket_pk, user_pk, bucket_owner="APP"):
    try:
        datasource = S3Bucket.objects.get(pk=bucket_pk)
    except S3Bucket.DoesNotExist as exc:
        # nothing to do, dont want to be added back to queue, so return
        print(f"BUCKET NOT FOUND FOR PK {bucket_pk}")
        raise self.retry(exc=exc, countdown=5)

    # TODO use the user_pk to check user permission

    # TODO bucket_owner should be passed by the task?
    datasource.cluster.create(owner=bucket_owner)


@shared_task(bind=True, max_retries=3)
def grant_user_s3bucket_access(self, bucket_pk, user_pk):
    try:
        user = User.objects.get(pk=user_pk)
        # TODO check user has permission?
    except User.DoesNotExist:
        # nothing to do, dont want to be added back to queue, so return
        return

    try:
        user_bucket = UserS3Bucket.objects.get(pk=bucket_pk)
    except UserS3Bucket.DoesNotExist as exc:
        # try again in case the bucket not yet created
        raise self.retry(exc=exc, countdown=5)

    cluster.User(user).grant_bucket_access(
        user_bucket.s3bucket.arn,
        user_bucket.access_level,
        user_bucket.resources,
    )


@shared_task(bind=True, max_retries=3)
def grant_app_s3bucket_access(self, app_s3_bucket_pk, user_pk):

    # TODO lookup user and check if they have permission

    try:
        bucket = AppS3Bucket.objects.get(pk=app_s3_bucket_pk)
    except AppS3Bucket.DoesNotExist as exc:
        raise self.retry(exc=exc, countdown=5)

    cluster.App(bucket.app).grant_bucket_access(
        bucket.s3bucket.arn,
        bucket.access_level,
        bucket.resources,
    )
