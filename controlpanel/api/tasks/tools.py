# Third-party
from celery import shared_task


# TODO do we need to use acks_late?
@shared_task(acks_on_failure_or_timeout=False)
def retire_tool(tool_pk):
    # First-party/Local
    from controlpanel.api.models.tool import Tool

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
    from controlpanel.api.cluster import ToolDeploymentError
    from controlpanel.api.models.tool import ToolDeployment

    try:
        tool_deployment = ToolDeployment.objects.active().get(pk=tool_deployment_pk)
    except ToolDeployment.DoesNotExist:
        return

    try:
        tool_deployment.uninstall()
    except ToolDeploymentError as e:
        # TODO update this to catch an error specificly about release not found, and let other
        # errors bubble up e.g. connection/authentication errors
        print(e)
