from celery import shared_task, Task

from controlpanel import celery_app
from controlpanel.api import cluster
from controlpanel.api.models import App, User, S3Bucket, UserS3Bucket, AppS3Bucket


class BaseTaskHandler(Task):

    model = None
    # can be applied to project settings
    acks_late = True
    acks_on_failure_or_timeout = False

    def get_object(self, pk):
        try:
            return self.model.objects.get(pk=pk)
        except self.model.DoesNotExist as exc:
            print(exc)
            raise exc

    def get_user(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist as exc:
            print(exc)
            raise exc

    def complete(self):
        from controlpanel.api.models import Task as TaskModel
        task = TaskModel.objects.filter(task_id=self.request.id).first()
        if task:
            task.completed = True
            task.save()

# @shared_task(acks_late=True, acks_on_failure_or_timeout=False)
# def create_app_auth_settings(app_pk, user_pk, envs, disable_authentication, connections):
#     try:
#         app = App.objects.get(pk=app_pk)
#     except App.DoesNotExist as exc:
#         print(exc)
#         raise exc
#
#     try:
#         user = User.objects.get(pk=user_pk)
#     except User.DoesNotExist:
#         # user doesnt exist, nothing to do, dont want to retry so return early
#         return
#
#     if not user.github_api_token:
#         # user doesnt have a githubapi token, log this?
#         return
#
#     for env in envs:
#         cluster.App(app, user.github_api_token).create_auth_settings(
#             env_name=env,
#             disable_authentication=disable_authentication,
#             connections=connections,
#         )


class CreateAppAuthSettings(BaseTaskHandler):
    model = App
    name = "create_app_auth_settings"

    def run(self, app_pk, user_pk, envs, disable_authentication, connections):
        app = self.get_object(pk=app_pk)
        user = self.get_user(pk=user_pk)
        if not user.github_api_token:
            return

        for env in envs:
            cluster.App(app, user.github_api_token).create_auth_settings(
                env_name=env,
                disable_authentication=disable_authentication,
                connections=connections,
            )
        self.complete()

# @shared_task(acks_late=True, acks_on_failure_or_timeout=False)
# def create_s3bucket(bucket_pk, user_pk, bucket_owner="APP"):
#     try:
#         datasource = S3Bucket.objects.get(pk=bucket_pk)
#     except S3Bucket.DoesNotExist as exc:
#         # nothing to do, dont want to be added back to queue, so return
#         print(exc)
#         raise exc
#
#     # TODO use the user_pk to check user permission
#
#     # TODO bucket_owner should be passed by the task?
#     datasource.cluster.create(owner=bucket_owner)


class CreateS3Bucket(BaseTaskHandler):

    model = S3Bucket
    name = "create_s3bucket"

    def run(self, bucket_pk, user_pk, bucket_owner="APP"):
        bucket = self.get_object(pk=bucket_pk)
        # this will already have run when the obj was created via modelform validation.
        # Is it unnecessary to call again?
        if cluster.S3Bucket(bucket).exists(bucket.name, bucket_owner=bucket_owner):
            return

        # TODO verify user?

        bucket.cluster.create(owner=bucket_owner)


# @shared_task(acks_late=True, acks_on_failure_or_timeout=False)
# def create_app_aws_role(app_pk):
#     try:
#         app = App.objects.get(pk=app_pk)
#     except App.DoesNotExist as exc:
#         print(exc)
#         raise exc
#
#     # this will catch when a role already exists
#     cluster.App(app).create_iam_role()


class CreateAppAWSRole(BaseTaskHandler):
    model = App
    name = "create_app_aws_role"

    def run(self, app_pk, user_pk):
        app = self.get_object(pk=app_pk)

        # TODO verify user?
        # user = self.get_user(pk=user_pk)

        cluster.App(app).create_iam_role()
        self.complete()


# @shared_task(acks_late=True, acks_on_failure_or_timeout=False)
# def grant_app_s3bucket_access(app_s3_bucket_pk, user_pk):
#
#     # TODO lookup user and check if they have permission
#
#     try:
#         bucket = AppS3Bucket.objects.get(pk=app_s3_bucket_pk)
#     except AppS3Bucket.DoesNotExist as exc:
#         print(exc)
#         raise exc
#
#     cluster.App(bucket.app).grant_bucket_access(
#         bucket.s3bucket.arn,
#         bucket.access_level,
#         bucket.resources,
#     )


class GrantAppS3BucketAccess(BaseTaskHandler):

    model = AppS3Bucket
    name = 'grant_app_s3bucket_access'

    def run(self, app_s3_bucket_pk, user_pk):
        app_bucket = self.get_object(pk=app_s3_bucket_pk)

        # TODO verify user?

        cluster.App(app_bucket.app).grant_bucket_access(
            app_bucket.s3bucket.arn,
            app_bucket.access_level,
            app_bucket.resources,
        )


# @shared_task(acks_late=True, acks_on_failure_or_timeout=False)
# def grant_user_s3bucket_access(bucket_pk, user_pk):
#     try:
#         user = User.objects.get(pk=user_pk)
#         # TODO check user has permission?
#     except User.DoesNotExist:
#         # nothing to do, dont want to be added back to queue, so return
#         return
#
#     try:
#         user_bucket = UserS3Bucket.objects.get(pk=bucket_pk)
#     except UserS3Bucket.DoesNotExist as exc:
#         # try again in case the bucket not yet created
#         print(exc)
#         raise exc
#
#     cluster.User(user).grant_bucket_access(
#         user_bucket.s3bucket.arn,
#         user_bucket.access_level,
#         user_bucket.resources,
#     )


class GrantUserS3BucketAccess(BaseTaskHandler):

    model = UserS3Bucket
    name = "grant_user_s3bucket_access"

    def run(self, bucket_pk, user_pk):
        user_bucket = self.get_object(pk=bucket_pk)
        user = self.get_user(pk=user_pk)

        # TODO verify user?

        cluster.User(user).grant_bucket_access(
            user_bucket.s3bucket.arn,
            user_bucket.access_level,
            user_bucket.resources,
        )


# @shared_task(acks_late=True, acks_on_failure_or_timeout=False)
# def grant_user_s3bucket_access(bucket_pk, user_pk):
#     try:
#         user = User.objects.get(pk=user_pk)
#         # TODO check user has permission?
#     except User.DoesNotExist:
#         # nothing to do, dont want to be added back to queue, so return
#         return
#
#     try:
#         user_bucket = UserS3Bucket.objects.get(pk=bucket_pk)
#     except UserS3Bucket.DoesNotExist as exc:
#         # try again in case the bucket not yet created
#         print(exc)
#         raise exc
#
#     cluster.User(user).grant_bucket_access(
#         user_bucket.s3bucket.arn,
#         user_bucket.access_level,
#         user_bucket.resources,
#     )

create_app_aws_role = celery_app.register_task(CreateAppAWSRole())
create_s3bucket = celery_app.register_task(CreateS3Bucket())
grant_app_s3bucket_access = celery_app.register_task(GrantAppS3BucketAccess())
grant_user_s3bucket_access = celery_app.register_task(GrantUserS3BucketAccess())
create_app_auth_settings = celery_app.register_task(CreateAppAuthSettings())
