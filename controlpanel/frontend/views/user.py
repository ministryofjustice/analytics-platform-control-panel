import dateutil.parser
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import DeleteView, UpdateView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

from controlpanel.api import auth0
from controlpanel.api.models import User


class UserList(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    permission_required = 'api.list_user'
    queryset = User.objects.exclude(auth0_id='')
    template_name = "user-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        users = auth0.ManagementAPI().list_users(
            params={
                'q': 'identities.connection:"github"'
            },
        )

        last_logins = []
        for user in users:
            auth0_id = user['user_id']

            if auth0_id == '':
                continue

            try:
                last_login = dateutil.parser.parse(user.get('last_login'))
            except (TypeError, ValueError):
                last_login = None

            last_logins.append((auth0_id, last_login))

        context['last_login'] = dict(last_logins)

        return context


class UserDelete(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = User
    permission_required = 'api.destroy_user'

    def get_success_url(self):
        messages.success(self.request, "Successfully deleted user")
        return reverse_lazy("list-users")


class UserDetail(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = User
    permission_required = 'api.retrieve_user'
    template_name = "user-detail.html"


class SetSuperadmin(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    fields = ['is_superuser']
    http_method_names = ['post']
    model = User
    permission_required = 'api.dd_superuser'

    def get_success_url(self):
        messages.success(self.request, "Successfully updated superadmin status")
        return reverse_lazy("manage-user", kwargs={"pk": self.object.auth0_id})


class ResetMFA(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    SingleObjectMixin,
    RedirectView,
):
    model = User
    permission_required = 'api.reset_mfa'

    def get_redirect_url(self, *args, **kwargs):
        user = self.get_object()
        user.reset_mfa()
        messages.success(self.request, "User MFA reset successfully")
        return reverse_lazy("manage-user", kwargs={"pk": user.auth0_id})
