# Third-party
import structlog
from celery import shared_task

# First-party/Local
from controlpanel.api import cluster, helm
from controlpanel.utils import _get_model

log = structlog.getLogger(__name__)


# TODO do we need to use acks_late? try without first
@shared_task(acks_on_failure_or_timeout=False)  # this does nothing without using acks_late
def uninstall_tool(tool_pk):
    Tool = _get_model("Tool")
    try:
        tool = Tool.objects.get(pk=tool_pk)
    except Tool.DoesNotExist:
        return

    for tool_deployment in tool.tool_deployments.active():
        uninstall_helm_release.delay(tool_deployment.k8s_namespace, tool_deployment.release_name)


@shared_task(acks_on_failure_or_timeout=False)
def uninstall_helm_release(namespace, release_name):
    try:
        helm.delete(namespace, release_name)
    except helm.HelmReleaseNotFound as e:
        log.info(e)


@shared_task
def reset_home_directory(user_id):
    user = _get_model("User").objects.get(auth0_id=user_id)
    cluster.User(user).reset_home()
