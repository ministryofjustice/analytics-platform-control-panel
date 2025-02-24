# Third-party
from celery import shared_task

# First-party/Local
from controlpanel.api import cluster
from controlpanel.utils import _get_model


@shared_task(acks_on_failure_or_timeout=False)
def upgrade_user_helm_chart(username, chart_name):
    User = _get_model("User")
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return
    cluster_user = cluster.User(user)
    chart = cluster_user.get_helm_chart(chart_name)
    cluster_user._run_helm_install_command(chart)
