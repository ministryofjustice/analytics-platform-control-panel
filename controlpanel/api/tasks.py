from celery import shared_task

from controlpanel.api import cluster
from controlpanel.api.models import App, User


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
        raise self.retry(exc=exc, countdown=5, throw=False)

    # this will catch when a role already exists
    cluster.App(app).create_iam_role()


@shared_task(bind=True)
def create_app_auth_settings(self, app_pk, user_pk, envs, disable_authentication, connections):
    try:
        app = App.objects.get(pk=app_pk)
    except App.DoesNotExist as exc:
        # the app does not exist, so add message back to the queue. Is this the best way?
        raise self.retry(exc=exc, countdown=5)

    user = User.objects.get(pk=user_pk)
    if not user.github_api_token:
        # user doesnt have a githubapi token, log this?
        return

    for env in envs:
        cluster.App(app, user.github_api_token).create_auth_settings(
            env_name=env,
            disable_authentication=disable_authentication,
            connections=connections,
        )



# @shared_task
# def grant_user_bucket_access_task(user_pk, arn, access_level, resources):
#     user = User.objects.get(pk=user_pk)
#     cluster.User(user).grant_bucket_access(
#         arn,
#         access_level,
#         resources,
#     )

