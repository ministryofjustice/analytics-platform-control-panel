# Third-party
import structlog
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormMixin, UpdateView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import App
from controlpanel.frontend.forms import AppSecretForm, AppSecretUpdateForm
from controlpanel.oidc import OIDCLoginRequiredMixin

log = structlog.getLogger(__name__)


class AppSecretMixin(OIDCLoginRequiredMixin, PermissionRequiredMixin):
    model = App
    permission_required = "api.update_app_settings"
    allowed_methods = ["POST"]

    def _format_key_name(self, key):
        return key

    def form_valid(self, form):
        app = self.get_object()
        cluster.App(app, self.request.user.github_api_token).create_or_update_secret(
            env_name=form.cleaned_data.get("env_name"),
            secret_key=self._format_key_name(form.cleaned_data["key"]),
            secret_value=form.cleaned_data.get("value"),
        )
        return HttpResponseRedirect(self.get_success_url(app_id=app.id))

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        data = self.request.GET.dict()
        kwargs["initial"]["env_name"] = data.get("env_name")
        kwargs["initial"]["key"] = self.kwargs.get("secret_name")
        kwargs["initial"]["display_key"] = cluster.App.get_github_key_display_name(
            self.kwargs.get("secret_name"))
        return kwargs

    def get_success_url(self, app_id):
        messages.success(self.request, "Successfully finished the action")
        return reverse_lazy("manage-app", kwargs={"pk": app_id})


class AppSecretCreate(AppSecretMixin, UpdateView):
    form_class = AppSecretForm
    template_name = "app-secret-create.html"

    def _format_key_name(self, key):
        return cluster.App.format_github_key_name(key)


class AppSecretUpdate(AppSecretMixin, UpdateView):
    form_class = AppSecretUpdateForm
    template_name = "app-secret-update.html"


class AppSecretDelete(AppSecretMixin, SingleObjectMixin, RedirectView):
    def post(self, request, *args, **kwargs):
        app = self.get_object()
        env_names = dict(self.request.POST).get("env_name")
        env_name = env_names[0] if env_names else None
        cluster.App(app, self.request.user.github_api_token).delete_secret(
            env_name=env_name,
            secret_name=self.kwargs["secret_name"],
        )
        return HttpResponseRedirect(self.get_success_url(app.id))
