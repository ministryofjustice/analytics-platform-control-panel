from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView
from django.views.generic.edit import FormMixin, DeleteView
from rules.contrib.views import PermissionRequiredMixin

from controlpanel.api import cluster
from controlpanel.api.models import Parameter
from controlpanel.api.models.parameter import APP_TYPE_CHOICES
from controlpanel.api.permissions import is_superuser
from controlpanel.frontend.forms import CreateParameterForm
from controlpanel.oidc import OIDCLoginRequiredMixin


class ParameterList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = 'parameters'
    model = Parameter
    permission_required = 'api.list_parameter'
    template_name = "parameter-list.html"

    def get_queryset(self):
        return Parameter.objects.filter(created_by=self.request.user)


class AdminParameterList(ParameterList):
    permission_required = 'api.is_superuser'

    def get_queryset(self):
        return Parameter.objects.all()


class ParameterCreate(OIDCLoginRequiredMixin, PermissionRequiredMixin, CreateView):
    form_class = CreateParameterForm
    model = Parameter
    permission_required = 'api.create_parameter'
    template_name = "parameter-create.html"

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_success_url(self):
        return reverse_lazy("list-parameters")

    def form_valid(self, form):
        self.object = Parameter(
            key=form.cleaned_data['key'],
            role_name=form.cleaned_data['role_name'],
            app_type=form.cleaned_data['app_type'],
            description="",
            created_by=self.request.user
        )
        self.object.value = form.cleaned_data['value']
        self.object.save()
        messages.success(
            self.request,
            f"Successfully created {self.object.name} parameter",
        )
        return FormMixin.form_valid(self, form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['app_type_choices'] = [
            {"text": c[1], "value": c[0]}
            for c in APP_TYPE_CHOICES
        ]
        return context



class ParameterDelete(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Parameter
    permission_required = 'api.destroy_parameter'

    def get_success_url(self):
        messages.success(self.request, "Successfully delete data source")
        return reverse_lazy("list-parameters")

    def get_queryset(self):
        queryset = Parameter.objects.all()
        if is_superuser(self.request.user):
            return queryset
        return queryset.filter(created_by=self.request.user)


class ParameterFormRoleList(OIDCLoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        roles = cluster.list_role_names()
        data = [
            r for r in roles
            if r.startswith(f"airflow")
            or r.startswith(f"{settings.ENV}_app")
        ]
        return JsonResponse(data, safe=False)
