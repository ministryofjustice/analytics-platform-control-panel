# Third-party
from celery import shared_task

# First-party/Local
from controlpanel.api import helm
from controlpanel.utils import _get_model


# TODO do we need to use acks_late? try without first
@shared_task(acks_on_failure_or_timeout=False)
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
        print(e)
