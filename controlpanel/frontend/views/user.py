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
    return datetime.now() - timedelta(days=90)


class UserList(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = 'users'
    model = User
    permission_required = 'api.list_user'
    queryset = User.objects.exclude(auth0_id='')
    template_name = "user-list.html"

    def get_context_data(self, **kwargs):
        # TODO: Refactor this. I've added annotations for future reference.
        context = super().get_context_data(**kwargs)

        # This returns a list of dictionary objects from Auth0. Each dictionary
        # represents a user.
        users = auth0.ManagementAPI().list_users(
            params={
                'q': 'identities.connection:"github"'
            },
        )

        # We also need the django.contrib.auth.User instances for each user
        # too. The auth0_mapper dictionary stores a User instance for each user
        # against their Auth0 ID (so we can connect them to the dictionary
        # related record from Auth0 -- see above). These objects are used as a
        # fallback for when we don't have a last_login for the user from Auth0.
        auth0_mapper = {}
        for db_user in self.queryset:
            if db_user.auth0_id:
                auth0_mapper[db_user.auth0_id] = db_user

        # This dictionary will store details of last logins for those users for
        # whom such data is available (apparently, not all users may have
        # logged in). TODO: Investigate if this is actually the case. Surely
        # all users must have logged in to set up their account and get
        # registered via Auth0.
        last_logins = {}
        for user in users:
            auth0_id = user['user_id']
            # Apparently some Auth0 users won't have a "user_id". TODO: WAT?
            # Check if this is the case.
            if auth0_id == '':
                continue
            # This next block is a confusing mess. TODO: Investigate is we
            # can't just use Django's User model's last_login field.
            last_login = None
            try:
                # First check the Auth0 based record / dictionary.
                auth0_last_login = user.get("last_login")
                if auth0_last_login:
                    last_login = dateutil.parser.parse(user.get('last_login'))
                else: 
                    # Fall back to Django's User model's last_login field.
                    db_user = auth0_mapper.get(auth0_id, None)
                    if db_user:
                        last_login = db_user.last_login
            except (TypeError, ValueError):
                last_login = None
            # Only add a last_login record to the context if there's something
            # to add.
            if last_login:
                last_logins[auth0_id] = {
                    # The datetime of last login to display in the template.
                    "last_login": last_login,
                    # Not logged in for 90 days? Perhaps the account is unused
                    # so set this flag to indicate the account should be
                    # checked by a human for legitimate inactivity and thus
                    # removal from the system.
                    "unused": last_login.utcnow() < ninety_days_ago(),
                }

        context['last_login'] = last_logins
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
        # account maybe unused and so a candidate for removal.
        context["unused"] = self.object.last_login.utcnow() < ninety_days_ago()
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
