# Third-party
import requests
import structlog
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.views.generic.base import RedirectView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import CreateView, UpdateView, FormMixin
from django.urls import reverse_lazy
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import App
from controlpanel.oidc import OIDCLoginRequiredMixin
from controlpanel.frontend.forms import AppVariableForm, AppVariableUpdateForm, DisableAuthForm


log = structlog.getLogger(__name__)


class AppVariableMixin(OIDCLoginRequiredMixin, PermissionRequiredMixin):
    model = App
    allowed_methods = ["POST"]
    template_name = "app-variable-manage.html"
    permission_required = "api.update_app"

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        data = self.request.GET.dict()
        kwargs["initial"]["env_name"] = data.get("env_name")
        kwargs["initial"]["key"] = self.kwargs.get('var_name')
        if kwargs["initial"]["key"]:
            try:
                var_info = cluster.App(self.get_object()).get_env_var(
                    github_token=self.request.user.github_api_token,
                    env_name=kwargs["initial"]["env_name"],
                    key_name=kwargs["initial"]["key"])
            except requests.exceptions.HTTPError as error:
                if error.response.status_code == 404:
                    var_info = {}
                else:
                    raise Exception(str(error))
            kwargs["initial"]["value"] = var_info.get('value', '')
        return kwargs

    def get_success_url(self, app_id):
        messages.success(self.request, "Successfully finished the action")
        return reverse_lazy("manage-app", kwargs={"pk": app_id})


class AppVariableCreate(AppVariableMixin, CreateView):
    form_class = AppVariableForm

    def form_valid(self, form):
        app = self.get_object()
        cluster.App(app).create_or_update_env_var(
            github_token=self.request.user.github_api_token,
            env_name=form.cleaned_data.get("env_name"),
            key_name=form.cleaned_data["key"],
            key_value=form.cleaned_data.get("value"))
        return HttpResponseRedirect(self.get_success_url(app_id=app.id))


class AppVariableUpdate(AppVariableMixin, UpdateView):
    form_class = AppVariableUpdateForm

    def get_form_class(self):
        key_name = self.kwargs.get('var_name')
        if key_name == cluster.App.AUTHENTICATION_REQUIRED:
            return DisableAuthForm
        else:
            return super().get_form_class()

    def form_valid(self, form):
        app = self.get_object()
        cluster.App(app).create_or_update_env_var(
            github_token=self.request.user.github_api_token,
            env_name=form.cleaned_data.get("env_name"),
            key_name=form.cleaned_data["key"],
            key_value=form.cleaned_data.get("value"))
        return HttpResponseRedirect(self.get_success_url(app_id=app.id))


class AppVariableDelete(AppVariableMixin, SingleObjectMixin, RedirectView):

    def post(self, request, *args, **kwargs):
        app = self.get_object()
        env_name = dict(self.request.POST).get('env_name')[0]
        cluster.App(app).delete_env_var(
            self.request.user.github_api_token,
            env_name=env_name,
            key_name=self.kwargs["var_name"])
        return HttpResponseRedirect(self.get_success_url(app_id=app.id))
