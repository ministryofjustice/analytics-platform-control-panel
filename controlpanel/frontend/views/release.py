# Third-party
from django.contrib import messages
from django.db.models import Count, Q
from django.http.response import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.models import Tool
from controlpanel.frontend.filters import ReleaseFilter
from controlpanel.frontend.forms import ToolReleaseForm
from controlpanel.oidc import OIDCLoginRequiredMixin


class ReleaseList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Used to display a list of releases of the tools available in the control
    panel application.
    """

    context_object_name = "releases"
    model = Tool
    permission_required = "api.list_tool_release"
    template_name = "release-list.html"
    ordering = ["name", "-version", "-created"]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.annotate(
            num_users=Count(
                "tool_deployments", distinct=True, filter=Q(tool_deployments__is_active=True)
            )
        )
        return qs

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context["filter"] = ReleaseFilter(self.request.GET, queryset=self.get_queryset())
        context[self.context_object_name] = context["filter"].qs.distinct()
        return context


class ReleaseDelete(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Deletes a release for a tool from the control panel application.
    """

    model = Tool
    permission_required = "api.destroy_tool_release"

    def get_success_url(self):
        messages.success(self.request, "Successfully deleted release")
        return reverse_lazy("list-tool-releases")


class ReleaseDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Displays and allows editing of a specific release.
    """

    form_class = ToolReleaseForm
    context_object_name = "release"
    model = Tool
    permission_required = "api.update_tool_release"
    template_name = "release-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_users = []
        for user in self.object.target_users.all():
            target_users.append(user.username)
        context["target_users"] = ", ".join(target_users)
        return context

    def form_valid(self, form):
        """
        Ensure the object is updated as expected (for the beta-users).
        """
        self.object = form.save()
        target_list = form.cleaned_data["target_users_list"]
        if target_list:
            self.object.target_users.set(target_list)
        else:
            self.object.target_users.clear()
        messages.success(self.request, "Successfully updated release")
        return HttpResponseRedirect(reverse_lazy("list-tool-releases"))


class ReleaseCreate(OIDCLoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Create a new release of a tool on the analytic platform.
    """

    form_class = ToolReleaseForm
    context_object_name = "release"
    model = Tool
    permission_required = "api.create_tool_release"
    template_name = "release-create.html"

    def form_valid(self, form):
        """
        Ensure the object is created as expected (with the beta-users).
        """
        self.object = form.save()
        target_list = form.cleaned_data["target_users_list"]
        if target_list:
            self.object.target_users.set(target_list)
        messages.success(self.request, "Successfully created new release")
        return HttpResponseRedirect(reverse_lazy("list-tool-releases"))
