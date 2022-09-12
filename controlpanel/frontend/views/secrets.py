import secrets
from typing import Optional
from controlpanel.frontend.forms import SecretsForm, DisableAuthForm
from controlpanel.oidc import OIDCLoginRequiredMixin
from rules.contrib.views import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.http import Http404, HttpResponseRedirect

from controlpanel.api.models import App
from controlpanel.api import aws

from django.views.generic import TemplateView
from django.views.generic.edit import FormView, DeletionMixin


class AppSecretMixin:
    def _get_app(self, pk) -> Optional[App]:
        # get app from pk
        return get_object_or_404(App, pk=pk)
    
    def get_success_url(self) -> str:
        return reverse_lazy(self.success_url, kwargs={'pk': self.kwargs.get('pk')})


class SecretAddViewSet(OIDCLoginRequiredMixin, PermissionRequiredMixin, AppSecretMixin, TemplateView):
    permission_required = 'api.create_app'
    template_name = 'secret-view-variable.html'
    allowed_secrets = {
        'generic': SecretsForm,
        'disable_authentication': DisableAuthForm
    }
    success_url = 'manage-app'

    def get(self, request, pk=None, *args, **kwargs):
        # get all set secrets
        app = self._get_app(pk)
        set_secrets = aws.AWSSecretManager().get_secret_if_found(app.app_aws_secret_name)
        set_secrets = ['disable_authentication']
        set_secrets = [key for key, _ in self.allowed_secrets.items() if key in set_secrets]

        return super(SecretAddViewSet, self).get(request, *args, pk=pk, set_secrets=set_secrets, **kwargs)

    def get_context_data(self, *args, pk=None, **kwargs):
        context = super(SecretAddViewSet, self).get_context_data(**kwargs)
        context['forms'] = self.allowed_secrets
        context['pk'] = pk        
        return context


class SecretAddUpdate(OIDCLoginRequiredMixin, PermissionRequiredMixin, AppSecretMixin, FormView):
    permission_required = 'api.create_app'
    template_name = 'secret-add-variable.html'
    success_url = 'view-secret'
    allowed_keys = {
        'generic': SecretsForm,
        'disable_authentication': DisableAuthForm,
    }

    def get_form(self, form_class):
        # secret_key received from the url
        form_key = self.kwargs.get('secret_key', 'generic')
        form_class = self.allowed_keys.get(form_key)
        return form_class

    def get_context_data(self, **kwargs):
        secret_key = self.kwargs.get('secret_key')
        form = self.allowed_keys.get(secret_key)()
        return super(SecretAddUpdate, self).get_context_data(secret_key=secret_key, form=form, **kwargs)

    def form_valid(self, form):
        secret_key = self.kwargs.get('secret_key')
        secret_value = form.cleaned_data.get('secret_value')
        app = self._get_app(self.kwargs.get('pk'))

        if not self.allowed_keys.get(secret_key):
            raise Http404("Invalid Webapp")

        # update secret key
        aws.AWSSecretManager().create_or_update(app.app_aws_secret_name, {'secret_key': secret_value})
        return super(SecretAddUpdate, self).form_valid(form)


class SecretDelete(OIDCLoginRequiredMixin, PermissionRequiredMixin, AppSecretMixin, DeletionMixin, TemplateView):
    success_url = 'view-secret'
    permission_required = 'api.create_app'

    def delete(self, request, *args, pk=None, secret_key=None, **kwargs):
        """
        Override DeleteMixing method
        """
        app = self._get_app(pk)
        if not aws.AWSSecretManager().get_secret_if_found(app.app_aws_secret_name):
            raise Http404('Failed to find the secret you want to delete.')

        aws.AWSSecretManager().delete_secret(secret_key)
        success_url = self.get_success_url()
        return HttpResponseRedirect(success_url)

    