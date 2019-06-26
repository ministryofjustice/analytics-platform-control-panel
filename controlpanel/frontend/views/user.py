import dateutil.parser
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import DeleteView, UpdateView
from django.views.generic.list import ListView

from controlpanel.api import auth0
from controlpanel.api.models import User


class UserList(LoginRequiredMixin, ListView):
    model = User
    template_name = "user-list.html"
    queryset = User.objects.exclude(auth0_id='')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        users = auth0.ManagementAPI().list_users()

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


class UserDelete(LoginRequiredMixin, DeleteView):
    model = User

    def get_success_url(self):
        messages.success(self.request, "Successfully deleted user")
        return reverse_lazy("list-users")


class UserDetail(LoginRequiredMixin, DetailView):
    model = User
    template_name = "user-detail.html"


class SetSuperadmin(LoginRequiredMixin, UpdateView):
    fields = ['is_superuser']
    model = User

    def get_success_url(self):
        messages.success(self.request, "Successfully updated superadmin status")
        return reverse_lazy("manage-user", kwargs={"pk": self.object.auth0_id})


class ResetMFA(LoginRequiredMixin, SingleObjectMixin, RedirectView):
    model = User

    def get_redirect_url(self, *args, **kwargs):
        user = self.get_object()
        user.reset_mfa()
        messages.success(self.request, "User MFA reset successfully")
        return reverse_lazy("manage-user", kwargs={"pk": user.auth0_id})
