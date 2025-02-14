# Third-party
from celery import shared_task
from django.apps import apps

# First-party/Local
from controlpanel.api import cluster, helm


def _get_model(model_name):
    """
    This is used to avoid a circular import when calling tasks from within models. I feel like this
    is the best worst option. For futher reading on this issue and the lack of an ideal solution:
    https://stackoverflow.com/questions/26379026/resolving-circular-imports-in-celery-and-django
    """
    return apps.get_model("api", model_name)


# TODO do we need to use acks_late?
@shared_task(acks_on_failure_or_timeout=False)
def uninstall_tool(tool_pk):
    Tool = _get_model("Tool")
    try:
        tool = Tool.objects.get(pk=tool_pk, is_retired=True)
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
