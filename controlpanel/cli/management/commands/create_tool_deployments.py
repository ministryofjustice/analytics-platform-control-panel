# Third-party
from django.core.management.base import BaseCommand
from django.db.models import Q

# First-party/Local
from controlpanel.api.kubernetes import KubernetesClient
from controlpanel.api.models import Tool, ToolDeployment, User


class Command(BaseCommand):

    MEMORY_DEFAULT = "12Gi"
    CPU_DEFAULT = "1"

    def handle(self, *args, **options):
        ToolDeployment.objects.all().delete()
        client = KubernetesClient(use_cpanel_creds=True)
        deployments = client.AppsV1Api.list_deployment_for_all_namespaces()
        for deployment in deployments.items:
            name = deployment.metadata.name
            # we only care about tool deployments
            if not name.startswith(("vscode", "jupyter", "rstudio")):
                continue

            # we don't care about the scheduler
            if "scheduler" in name:
                continue

            username = deployment.metadata.namespace.removeprefix("user-")
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stderr.write(
                    f"ERROR: failed to find user with username {username}, skipping\n---------------"  # noqa
                )
                continue
            # get the chart name, version, and use that to get the tool type
            chart_name, chart_version = deployment.metadata.labels.get("chart", "").rsplit("-", 1)
            tool_type = chart_name.split("-")[0]

            tool_container = None
            for container in deployment.spec.template.spec.containers:
                if "auth" not in container.name:
                    tool_container = container

            # get specific details about the deployed tool
            image_tag = tool_container.image.split(":")[-1]
            requests_memory = tool_container.resources.requests["memory"]
            requests_cpu = tool_container.resources.requests["cpu"]
            limits_memory = tool_container.resources.limits["memory"]
            gpu = deployment.spec.template.spec.node_selector == {"gpu-compute": "true"}

            self.stdout.write(f"Username: {username}")
            self.stdout.write(f"Name: {name}")
            self.stdout.write(f"Tool Type: {tool_type}")
            self.stdout.write(f"Chart Name: {chart_name}")
            self.stdout.write(f"Chart Version: {chart_version}")
            self.stdout.write(f"Image tag: {image_tag}")
            self.stdout.write(f"Requests Memory: {requests_memory}")
            self.stdout.write(f"Requests CPU: {requests_cpu}")
            self.stdout.write(f"Limits Memory: {limits_memory}")
            self.stdout.write(f"GPU: {gpu}")

            # include retired/restricted releases so we still have a record of which users were
            # using them. However they wont be displayed as an option to deploy if they have been
            # retired or restricted
            tool_queryset = Tool.objects.filter(
                image_tag=image_tag,
                version=chart_version,
                chart_name=chart_name,
            )

            # build up values to filter for specific releases if they dont match the defaults
            values = {}
            if requests_memory != self.MEMORY_DEFAULT:
                values[f"{tool_type}.resources.requests.memory"] = requests_memory
            if requests_cpu != self.CPU_DEFAULT:
                values[f"{tool_type}.resources.requests.cpu"] = requests_cpu
            if limits_memory != self.MEMORY_DEFAULT:
                values[f"{tool_type}.resources.limits.memory"] = limits_memory

            if values:
                tool_queryset = tool_queryset.filter(values__contains=values)

            # filter or exclude GPU releases
            if gpu:
                tool_queryset = tool_queryset.filter(values__contains={"gpu.enabled": "true"})
            else:
                tool_queryset = tool_queryset.exclude(values__contains={"gpu.enabled": "true"})

            # we should be down to a single release at this point but just in case use first
            tool = tool_queryset.first()
            if not tool:
                self.stderr.write("ERROR failed to find tool for these details\n")
                continue

            # if we have a tool, create a ToolDeployment record
            tool_deployment = ToolDeployment.objects.create(
                tool=tool, user=user, tool_type=tool_type, is_active=True
            )
            self.stdout.write(
                f"Created tool deployment for {username} with tool {tool_deployment.tool}\n---------------"  # noqa
            )
