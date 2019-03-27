import re

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView
from django.views.generic.list import ListView

from controlpanel.api.models import (
    App,
    User,
    UserApp,
)


class AppsList(LoginRequiredMixin, ListView):
    template_name = "webapp-list.html"

    def get_queryset(self):
        return [ua.app for ua in self.request.user.userapps.all()]


class AppDetail(LoginRequiredMixin, DetailView):
    model = App
    template_name = "webapp-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app = self.get_object()

        app_admins = [ua.user for ua in app.userapps.filter(is_admin=True)]
        context["app_admins"] = app_admins

        app_admins_ids = [user.auth0_id for user in app_admins]
        context["admin_options"] = User.objects.filter(
            auth0_id__isnull=False,
        ).exclude(
            auth0_id__in=app_admins_ids,
        )

        return context


class CreateApp(LoginRequiredMixin, CreateView):
    fields = ['repo_url']
    model = App
    success_url = reverse_lazy("list-apps")
    template_name = "webapp-create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['orgs'] = [
            {"name": org, "url": f"https://github.com/{org}"}
            for org in settings.GITHUB_ORGS
        ]
        return context


class DeleteApp(LoginRequiredMixin, DeleteView):
    model = App
    success_url = reverse_lazy("list-apps")

    def delete(self, request, *args, **kwargs):
        app = self.get_object()
        messages.success(self.request, f"Successfully deleted {app.name} app")
        return super().delete(request, *args, **kwargs)


class AddCustomers(LoginRequiredMixin, RedirectView):
    http_method_names = ["post"]

    def get_redirect_url(self, *args, **kwargs):
        app = get_object_or_404(App, pk=kwargs.get('pk'))
        emails = self.request.POST.get('customer_email')
        emails = re.split(r'[,; ]+', emails)
        emails = [email.strip() for email in emails]
        app.add_customers(emails)
        messages.success(self.request, f"Successfully added customers")
        return reverse_lazy("manage-app", kwargs=kwargs)


class RemoveCustomer(LoginRequiredMixin, RedirectView):
    http_method_names = ["post"]

    def get_redirect_url(self, *args, **kwargs):
        app = get_object_or_404(App, pk=kwargs.get('pk'))
        user_id = self.request.POST.get('customer')
        app.delete_customers([user_id])
        messages.success(self.request, "Successfully removed customer")
        return reverse_lazy("manage-app", kwargs=kwargs)


class AddAdmin(LoginRequiredMixin, SingleObjectMixin, RedirectView):
    http_method_names = ['post']
    model = App

    def get_redirect_url(self, *args, **kwargs):
        app = self.get_object()
        user = get_object_or_404(User, pk=self.request.POST['user_id'])
        userapp = UserApp.objects.create(
            app=app,
            user=user,
            is_admin=True,
        )
        userapp.save()
        messages.success(self.request, f"Granted admin access to {user.name}")
        return reverse_lazy("manage-app", kwargs={"pk": app.pk})


class RevokeAdmin(LoginRequiredMixin, SingleObjectMixin, RedirectView):
    model = App

    def get_redirect_url(self, *args, **kwargs):
        app = self.get_object()
        user = get_object_or_404(User, pk=kwargs['user_id'])
        userapp = get_object_or_404(UserApp, app=app, user=user)
        userapp.delete()
        messages.success(self.request, f"Revoked admin access for {user.name}")
        return reverse_lazy("manage-app", kwargs={"pk": app.pk})
