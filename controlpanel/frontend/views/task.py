# Third-party
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.models import Task
from controlpanel.oidc import OIDCLoginRequiredMixin


class TaskList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Used to display a list of incomplete tasks
    panel application.
    """

    context_object_name = "tasks"
    model = Task
    permission_required = "api.list_task"
    queryset = Task.objects.filter(completed=False)
    template_name = "task-list.html"
    ordering = ["entity_class", "entity_description", "created"]
