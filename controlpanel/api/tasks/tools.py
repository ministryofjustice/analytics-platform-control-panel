# Third-party
from celery import shared_task
from django.apps import apps


def _get_model(model_name):
    """
    This is used to avoid a circular import when calling tasks from within models. I feel like this
    is the best worst option. For futher reading on this issue and the lack of an ideal solution:
    https://stackoverflow.com/questions/26379026/resolving-circular-imports-in-celery-and-django
    """
    return apps.get_model("api", model_name)


# TODO do we need to use acks_late?
@shared_task(acks_on_failure_or_timeout=False)
def retire_tool(tool_pk):
    # First-party/Local
    Tool = _get_model("Tool")
    try:
        tool = Tool.objects.get(pk=tool_pk, is_retired=True)
    except Tool.DoesNotExist:
        return

    for tool_deployment in tool.tool_deployments.active():
        uninstall_tool_deployment.delay(tool_deployment.pk)


# TODO do we need to use acks_late? Not sure we can
@shared_task(acks_on_failure_or_timeout=False)
def uninstall_tool_deployment(tool_deployment_pk):
    # First-party/Local

    ToolDeployment = _get_model("ToolDeployment")
    try:
        tool_deployment = ToolDeployment.objects.active().get(pk=tool_deployment_pk)
    except ToolDeployment.DoesNotExist:
        return

    try:
        tool_deployment.uninstall()
    except ToolDeployment.Error as e:
        # TODO update this to catch an error specificly about release not found, and let other
        # errors bubble up e.g. connection/authentication errors
        print(e)
