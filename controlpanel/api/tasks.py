from celery import shared_task

from controlpanel.api import cluster
from controlpanel.api.models import App


@shared_task(bind=True, max_retries=3)
def create_app_aws_role(self, app_pk):
    try:
        app = App.objects.get(pk=app_pk)
    except App.DoesNotExist as exc:
        # the app does not exist, so add message back to the queue. Is this the best way?
        raise self.retry(exc=exc, countdown=5)

    # this will catch when a role already exists
    cluster.App(app).create_iam_role()


# @shared_task
# def grant_user_bucket_access_task(user_pk, arn, access_level, resources):
#     user = User.objects.get(pk=user_pk)
#     cluster.User(user).grant_bucket_access(
#         arn,
#         access_level,
#         resources,
#     )

