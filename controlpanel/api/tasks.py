from celery import shared_task
from controlpanel.api import cluster
from controlpanel.api.models import User


@shared_task()
def grant_user_bucket_access_task(user_pk, arn, access_level, resources):
    user = User.objects.get(pk=user_pk)
    cluster.User(user).grant_bucket_access(
        arn,
        access_level,
        resources,
    )
