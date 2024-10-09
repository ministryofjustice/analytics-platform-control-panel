# Third-party
from django.views.generic import DetailView, ListView
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
    queryset = Task.objects.exclude(completed=True)
    template_name = "task-list.html"


class TaskDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Task
    permission_required = "api.list_task"
    context_object_name = "task"
    template_name = "task-detail.html"
