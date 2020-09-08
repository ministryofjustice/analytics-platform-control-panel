import dateutil.parser
from datetime import datetime, timedelta
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


def three_months_ago():
    """
    Returns a datetime object referencing approximately three months in the
    past, from the current date. The assumption made here is that a month is
    roughly 30 days (so the result is always 90 days in the past).
    """
    return datetime.now() - timedelta(days=30*3)


class UserList(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = 'users'
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

        auth0_mapper = {}
        for db_user in self.queryset:
            if db_user.auth0_id:
                auth0_mapper[db_user.auth0_id] = db_user

        last_logins = []
        for user in users:
            auth0_id = user['user_id']

            if auth0_id == '':
                continue

            try:
                auth0_last_login = user.get("last_login")
                if auth0_last_login:
                    last_login = dateutil.parser.parse(user.get('last_login'))
                else: 
                    db_user = auth0_mapper.get(auth0_id, None)
                    if db_user:
                        last_login = db_user.last_login
            except (TypeError, ValueError):
                last_login = None

            last_logins.append((auth0_id, {
                "last_login": last_login,
                "unused": last_login.utcnow() < three_months_ago(),
            }))

        context['last_login'] = dict(last_logins)

        return context


class UserDelete(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = User
    permission_required = 'api.destroy_user'

    def get_success_url(self):
        messages.success(self.request, "Successfully deleted user")
        return reverse_lazy("list-users")


class UserDetail(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    context_object_name = 'user'
    model = User
    permission_required = 'api.retrieve_user'
    template_name = "user-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unused"] = self.object.last_login.utcnow() < three_months_ago()
        return context


class SetSuperadmin(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    fields = ['is_superuser']
    http_method_names = ['post']
    model = User
    permission_required = 'api.add_superuser'

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
