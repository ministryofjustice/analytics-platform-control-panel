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


def ninety_days_ago():
    """
    Returns a datetime object referencing approximately three months in the
    past, from the current date. The assumption made here is that a month is
    roughly 30 days (so the result is always 90 days in the past).
    """
    return datetime.now().date() - timedelta(days=90)


class UserList(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = 'users'
    model = User
    permission_required = 'api.list_user'
    queryset = User.objects.exclude(auth0_id='')
    template_name = "user-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_by = self.request.GET.get("o", "username")
        valid_fields = ["username", "email", "last_login", ]
        if order_by not in valid_fields:
            order_by = "username"
        unused_users = []
        for user in self.queryset.order_by(order_by):
            if user.last_login:
                if user.last_login.date() < ninety_days_ago():
                    unused_users.append(user)
            else:
                unused_users.append(user)
        context['unused_users'] = unused_users
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
        # A flag to indicate if the user hasn't logged in for 90 days - so the
        # account maybe unused and thus a candidate for removal.
        context["unused"] = None
        if self.object.last_login:
            context["unused"] = self.object.last_login.date() < ninety_days_ago()
        else:
            # No last login? They've never logged into the site.
            context["unused"] = True
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
