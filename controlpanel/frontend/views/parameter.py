# Third-party
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import FormMixin, FormView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import App, Parameter
from controlpanel.frontend.forms import CreateParameterForm
from controlpanel.oidc import OIDCLoginRequiredMixin


class ParameterList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = "parameters"
    model = Parameter
    permission_required = "api.list_parameter"
    template_name = "parameter-list.html"

    def get_queryset(self):
        return Parameter.objects.filter(created_by=self.request.user)


class AdminParameterList(ParameterList):
    permission_required = "api.is_superuser"

    def get_queryset(self):
        return Parameter.objects.all()


class ParameterCreate(OIDCLoginRequiredMixin, PermissionRequiredMixin, FormView):
    form_class = CreateParameterForm
    permission_required = "api.create_parameter"
    template_name = "parameter-create.html"

    def get_success_url(self):
        return reverse("manage-app", kwargs={"pk": self.kwargs.get("app_id")})

    def form_valid(self, form):
        """
        form values
        app_id, key, value
        """
        data = form.cleaned_data
        app_id = data.get("app_id")
        key, value = data.get("key"), data.get("value")

        app = App.objects.get(pk=app_id)
        manager = cluster.App(app)
        manager.create_or_update_secret(
            secret_name=app.app_aws_secret_param_name,
            secret_data={key: value})

        messages.success(
            self.request,
            f"Successfully created {key} parameter",
        )
        return FormMixin.form_valid(self, form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        data = self.request.GET.dict()
        if data.get("key"):
            kwargs["initial"]["key"] = data.get("key")
        return kwargs

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        app = App.objects.get(pk=self.kwargs.get("app_id"))

        form_data = self.get_form_kwargs()
        form_data["initial"] = {
            **form_data["initial"],
            "app_id": self.kwargs.get("app_id"),
        }

        form = CreateParameterForm(**form_data)
        context["form"] = form
        context["app"] = app
        return context


class ParameterDelete(OIDCLoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "api.destroy_parameter"

    def get(self, request, *args, **kwargs):
        data = request.GET.dict()
        app_id = data.get("app_id")
        key = data.get("key")
        app = App.objects.get(pk=app_id)
        manager = cluster.App(app)
        manager.delete_entries_in_secret(
            secret_name=app.app_aws_secret_param_name,
            keys_to_delete=[key])

        messages.success(
            self.request,
            f"Successfully deleted {key} parameter",
        )
        return redirect("manage-app", pk=app_id)


class ParameterFormRoleList(OIDCLoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        roles = cluster.App(None).list_role_names()
        data = [
            r
            for r in roles
            if r.startswith("airflow") or r.startswith(f"{settings.ENV}_app")
        ]
        return JsonResponse(data, safe=False)
