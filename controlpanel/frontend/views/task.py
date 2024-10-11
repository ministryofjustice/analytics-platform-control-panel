# Third-party
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.views.generic import DetailView, ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.message_broker import MessageBrokerClient
from controlpanel.api.models import Task
from controlpanel.api.tasks.utils import send_task
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

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")
        action = f"_{action}_task"
        getattr(self, action)()
        return HttpResponseRedirect(".")

    def _retry_task(self):
        self.object.cancelled = False
        self.object.retried_at = timezone.now()
        self.object.save()
        send_task(task=self.object)
        messages.success(self.request, "Task has been retried")

    def _cancel_task(self):
        self.object.cancelled = True
        self.object.save()
        messages.success(self.request, "Task has been cancelled")
