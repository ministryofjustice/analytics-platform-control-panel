# Standard library
from datetime import datetime, timedelta

# Third-party
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import Permission
from django.forms import BaseModelForm
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import DeleteView, FormView, UpdateView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.aws import AWSIdentityStore
from controlpanel.api.cluster import User as ClusterUser
from controlpanel.api.models import QUICKSIGHT_EMBED_AUTHOR_PERMISSION, User
from controlpanel.frontend import forms
from controlpanel.frontend.mixins import PolicyAccessMixin
from controlpanel.oidc import OIDCLoginRequiredMixin


def ninety_days_ago():
    """
    Returns a datetime object referencing approximately three months in the
    past, from the current date. The assumption made here is that a month is
    roughly 30 days (so the result is always 90 days in the past).
    """
    return datetime.now().date() - timedelta(days=90)


class UserList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = "users"
    model = User
    permission_required = "api.list_user"
    queryset = User.objects.exclude(auth0_id="")
    template_name = "user-list.html"

    def get_ordering(self):
        order_by = self.request.GET.get("o", "username")
        valid_fields = [
            "username",
            "email",
            "last_login",
        ]
        if order_by not in valid_fields:
            order_by = "username"
        return order_by

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        unused_users = []
        for user in self.queryset:
            if user.last_login:
                if user.last_login.date() < ninety_days_ago():
                    unused_users.append(user)
            else:
                unused_users.append(user)
        context["unused_users"] = unused_users
        return context


class UserDelete(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = User
    permission_required = "api.destroy_user"

    def get_success_url(self):
        messages.success(self.request, "Successfully deleted user")
        return reverse_lazy("list-users")


class UserDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    context_object_name = "user"
    model = User
    permission_required = "api.retrieve_user"
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


class SetSuperadmin(OIDCLoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "api.add_superuser"
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs["pk"])
        is_superuser = "is_superuser" in request.POST

        identity_store = AWSIdentityStore(
            settings.IDENTITY_CENTER_ASSUMED_ROLE,
            "APCPIdentityCenterAccess",
            settings.QUICKSIGHT_ACCOUNT_REGION,
        )

        if is_superuser:
            identity_store.add_user_to_group(
                user.justice_email, settings.QUICKSIGHT_AUTHOR_GROUP_NAME
            )
        else:
            identity_store.remove_user_from_group(
                user.justice_email, settings.QUICKSIGHT_AUTHOR_GROUP_NAME
            )

        user.is_superuser = is_superuser
        user.is_staff = is_superuser
        user.save()
        messages.success(self.request, "Successfully updated super admin status")
        return HttpResponseRedirect(reverse_lazy("manage-user", kwargs={"pk": user.auth0_id}))


class EnableBedrockUser(PolicyAccessMixin, UpdateView):
    model = User
    fields = ["is_bedrock_enabled"]
    success_message = "Successfully updated bedrock status"
    method_name = "set_bedrock_access"


class SetQuicksightAccess(OIDCLoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "api.add_superuser"
    http_method_names = ["post"]
    form_class = forms.QuicksightAccessForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user = get_object_or_404(User, pk=self.kwargs["pk"])
        kwargs.update({"user": user})
        return kwargs

    def form_valid(self, form):
        form.grant_access()
        messages.success(self.request, "Successfully updated Quicksight access")
        return HttpResponseRedirect(reverse_lazy("manage-user", kwargs={"pk": form.user.auth0_id}))

    def form_invalid(self, form):
        messages.error(self.request, "Failed to update Quicksight access")
        return HttpResponseRedirect(reverse_lazy("manage-user", kwargs={"pk": form.user.auth0_id}))


class ReinitialiseUser(OIDCLoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "api.add_superuser"
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs["pk"])
        cluster_user = ClusterUser(user)

        try:
            cluster_user.create()
            messages.success(self.request, "Reinitialised user successfully")
            return HttpResponseRedirect(reverse_lazy("manage-user", kwargs={"pk": user.auth0_id}))
        except Exception:
            messages.error(self.request, "Failed to reinitialise user")
            return HttpResponseRedirect(reverse_lazy("manage-user", kwargs={"pk": user.auth0_id}))


class EnableDatabaseAdmin(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    fields = ["is_database_admin"]
    http_method_names = ["post"]
    model = User
    permission_required = "api.add_superuser"

    def get_success_url(self):
        messages.success(self.request, "Successfully updated database admin status")
        return reverse_lazy("manage-user", kwargs={"pk": self.object.auth0_id})


class ResetMFA(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    SingleObjectMixin,
    RedirectView,
):
    model = User
    permission_required = "api.reset_mfa"

    def get_redirect_url(self, *args, **kwargs):
        user = self.get_object()
        user.reset_mfa()
        messages.success(self.request, "User MFA reset successfully")
        return reverse_lazy("manage-user", kwargs={"pk": user.auth0_id})
