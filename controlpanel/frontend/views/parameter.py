from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic.base import TemplateView
from django.views.generic import ListView, CreateView
from django.views.generic.edit import FormMixin, DeleteView
from rules.contrib.views import PermissionRequiredMixin

from django.views.generic.edit import FormView

from controlpanel.api import cluster
from controlpanel.api.models import Parameter
from controlpanel.api.models.parameter import APP_TYPE_CHOICES
from controlpanel.api.permissions import is_superuser
from controlpanel.frontend.forms import CreateParameterForm
from controlpanel.oidc import OIDCLoginRequiredMixin
from controlpanel.api.models import App
from controlpanel.api import cluster
from controlpanel.api.serializers import ParameterSerializer, ParamterEntrySerializer
from django.shortcuts import redirect
from django.views import View


class SecretsMixin:
    def get_manager(self, app: App):
        self.app = app
        self.secret_manager = cluster.App(app).set_secret_type('parameters')
        return self

    def _get_available_data(self):
        secret_data = self.secret_manager.get_secret_if_found()
        if 'items' not in secret_data:
            secret_data['items'] = []
        if 'name' not in secret_data:
            secret_data['name'] = self.app.name
        return secret_data

    def get_data(self) -> ParameterSerializer:
        secret_data = self._get_available_data()
        serial = ParameterSerializer(data=secret_data)
        serial.is_valid()
        return serial
    
    def get_redacted_data(self) -> dict:
        return self.get_data().current_keys()

    def update_or_create(self, key: str, value: str) -> ParameterSerializer:
        secret = self.get_data()
        secret_serial_new, action = secret.update_item(key, value)
        secret_serial_new.is_valid()

        self.secret_manager.create_or_update(secret_serial_new.data)
        return secret_serial_new

    def delete(self, key_to_delete) -> str:
        serial = self.get_data()
        secret_serial_new, delete_status = serial.delete_key(key_to_delete)      
        secret_serial_new.is_valid()
        self.secret_manager.create_or_update(secret_serial_new.data)
        return delete_status

    

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


class ParameterCreate(OIDCLoginRequiredMixin, PermissionRequiredMixin, SecretsMixin, FormView):
    form_class = CreateParameterForm
    permission_required = 'api.create_parameter'
    template_name = "parameter-create.html"

    def get_success_url(self):
        return reverse('manage-app', kwargs= {'pk': self.kwargs.get('app_id')})

    def form_valid(self, form):
        """
        form values
        app_id, key, value
        """
        data = form.cleaned_data
        app_id = data.get('app_id')
        key, value = data.get('key'), data.get('value')
        
        app = App.objects.get(pk = app_id)
        secret_serializer = self.get_manager(app).update_or_create(key, value)
        
        messages.success(
            self.request,
            f"Successfully created {key} parameter",
        )
        return FormMixin.form_valid(self, form)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        data = self.request.GET.dict()
        if data.get('key'):
            kwargs['initial']['key'] = data.get('key')
        return kwargs

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        app = App.objects.get(pk= self.kwargs.get('app_id'))

        form_data = self.get_form_kwargs()
        form_data['initial'] =  {**form_data['initial'], 'app_id': self.kwargs.get('app_id')}

        form = CreateParameterForm(**form_data)
        context['form'] = form
        context['app'] = app
        return context


class ParameterDelete(OIDCLoginRequiredMixin, PermissionRequiredMixin, SecretsMixin, View):
    permission_required = 'api.destroy_parameter'

    def get(self, request, *args, **kwargs):
        data = request.GET.dict()
        app_id = data.get('app_id')
        key = data.get('key')
        app = App.objects.get(pk=app_id)
        status = self.get_manager(app).delete(key)
        return redirect('manage-app', pk = app_id)


class ParameterFormRoleList(OIDCLoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        roles = cluster.App(None).list_role_names()
        data = [
            r for r in roles
            if r.startswith(f"airflow")
            or r.startswith(f"{settings.ENV}_app")
        ]
        return JsonResponse(data, safe=False)
