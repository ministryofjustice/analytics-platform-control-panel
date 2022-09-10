from django import forms
from controlpanel.frontend.forms import SecretsForm
from controlpanel.oidc import OIDCLoginRequiredMixin
from rules.contrib.views import PermissionRequiredMixin
from django.urls import reverse_lazy

from dataclasses import dataclass
from django.views.generic import TemplateView

@dataclass
class InputValue:
    key: str
    value: str
    form: forms.Form = SecretsForm


class SecretAddViewSet(OIDCLoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = 'api.create_app'
    template_name = 'secret-add-variable.html'
    allowed_secrets = [
        InputValue('disable_authentication', 'Disable Authentication')
    ]
    success_url = 'manage-app'
    
    def get_success_url(self) -> str:
        return reverse_lazy(self.success_url, kwargs={'pk': self.kwargs.get('pk')})

    def get(self, request, pk=None, *args, **kwargs):
        return super(SecretAddViewSet, self).get(request, pk=pk, *args, **kwargs)

    def post(self, request, pk=None, *args, **kwargs):
        return super(SecretAddViewSet, self).post(request, pk=pk, *args, **kwargs)

    def get_context_data(self, *args, pk=None, **kwargs):
        context = super(SecretAddViewSet, self).get_context_data(**kwargs)
        context['allowed_key_select'] = self.allowed_secrets
        context['pk'] = self.kwargs.get('pk')

        context['forms'] = {}
        for form in self.allowed_secrets:
            context['forms'][form.key] = form.form(initial={'secret_key': form.key})
        
        return context
