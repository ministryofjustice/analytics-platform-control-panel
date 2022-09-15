from http.client import HTTPResponse
import secrets
import structlog
from typing import Optional
from controlpanel.frontend.forms import DisableAuthForm
from controlpanel.oidc import OIDCLoginRequiredMixin
from rules.contrib.views import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.http import Http404, HttpResponseRedirect

from controlpanel.api.models import App
from controlpanel.api import aws

from django.views.generic import TemplateView
from django.views.generic.edit import View
from django.contrib import messages

log = structlog.getLogger(__name__)

ALLOWED_SECRETS = {
    # 'generic': SecretsForm,
    'disable_authentication': DisableAuthForm
}

class AppSecretMixin:
    def _get_app(self, pk) -> Optional[App]:
        # get app from pk
        return get_object_or_404(App, pk=pk)
    
    def get_success_url(self, message_type='added') -> str:
        messages.success(self.request, f"Successfully {message_type} secrets")
        return reverse_lazy(self.success_url, kwargs={'pk': self.kwargs.get('pk')})


class SecretAddUpdate(OIDCLoginRequiredMixin, PermissionRequiredMixin, AppSecretMixin, TemplateView):
    permission_required = 'api.update_app_secret'
    template_name = 'secret-add-variable.html'
    success_url = 'manage-app'

    def get_context_data(self, **kwargs):
        secret_key = self.kwargs.pop('secret_key')
        app = self._get_app(self.kwargs.get('pk'))

        if secret_key not in ALLOWED_SECRETS:
            raise Http404('Unable to access page. Invalid key.')

        # get stored current secret vars
        data = aws.AWSSecretManager().get_secret(app.app_aws_secret_name)
        form = ALLOWED_SECRETS.get(secret_key)(initial=dict(secret_value=data.get(secret_key)))
        return super(SecretAddUpdate, self).get_context_data(form=form, **kwargs)

    def form_valid(self, form):
        secret_key = self.kwargs.get('secret_key')
        secret_value = form.cleaned_data.get('secret_value')
        app = self._get_app(self.kwargs.get('pk'))

        if ALLOWED_SECRETS.get(secret_key) is None:
            raise Http404("Invalid Webapp")

        # update secret key
        aws.AWSSecretManager().create_or_update(app.app_aws_secret_name, {secret_key: secret_value})
        return super(SecretAddUpdate, self).form_valid(form)

    def post(self, request, pk=None, secret_key=None, **kwargs):
        form = ALLOWED_SECRETS.get(secret_key)(request.POST)

        if form.is_valid():
            secret_value = form.cleaned_data.get('secret_value')
            app = self._get_app(pk)
            aws.AWSSecretManager().create_or_update(app.app_aws_secret_name, {secret_key: secret_value})
        else:
            # currently, boolean values cannot fail, however will need to test this for non-bool values
            messages.error(self.request, "failed to update secrets.")
            return reverse_lazy('add-secret', kwargs={'pk': self.kwargs.get('pk'), 'secret_key': secret_key})
        return HttpResponseRedirect(self.get_success_url(message_type='updated'))


class SecretDelete(OIDCLoginRequiredMixin, PermissionRequiredMixin, AppSecretMixin, View):
    success_url = 'manage-app'
    permission_required = 'api.update_app_secret'
    allowed_methods = ['POST']

    def post(self, request, *args, pk=None, secret_key=None, **kwargs):
        """
        Override DeleteMixing method
        """
        app = self._get_app(pk)
        data: dict = aws.AWSSecretManager().get_secret_if_found(app.app_aws_secret_name)

        if secret_key not in data:
            log.error(f'trying to delete missing key {secret_key} from secrets')
            messages.error(self.request, f"failed to find {secret_key} in secrets")
            return HttpResponseRedirect(reverse_lazy(self.success_url, kwargs={'pk': self.kwargs.get('pk')}))

        aws.AWSSecretManager().update_secret(app.app_aws_secret_name, {}, delete_keys=[secret_key])
        return HttpResponseRedirect(self.get_success_url(message_type='deleted'))
