import re

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import (
    CreateView,
    DeleteView,
    FormMixin,
)
from django.views.generic.list import ListView
from github import Github
import requests

from controlpanel.api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
    User,
    UserApp,
    UserS3Bucket,
)
from controlpanel.frontend.forms import (
    CreateAppForm,
    GrantAppAccessForm,
)


class AppsList(LoginRequiredMixin, ListView):
    template_name = "webapp-list.html"
    all_apps = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_webapps'] = self.all_apps
        return context

    def get_queryset(self):
        if self.all_apps:
            return App.objects.all().prefetch_related('userapps')
        return [
            ua.app for ua in self.request.user.userapps.select_related('app').all()
        ]


class AppDetail(LoginRequiredMixin, DetailView):
    model = App
    template_name = "webapp-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app = self.get_object()
        admins = app.admins

        context["app_admins"] = admins

        context["admin_options"] = User.objects.filter(
            auth0_id__isnull=False,
        ).exclude(
            auth0_id__in=[user.auth0_id for user in admins],
        )

        context["grant_access_form"] = GrantAppAccessForm(
            app=app,
            exclude_connected=True,
        )

        return context


class CreateApp(LoginRequiredMixin, CreateView):
    form_class = CreateAppForm
    model = App
    template_name = "webapp-create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['repos'] = self.get_repositories()
        return context

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_repositories(self):
        repos = []
        github = Github(self.request.user.github_api_token)
        for name in settings.GITHUB_ORGS:
            org = github.get_organization(name)
            repos.extend(org.get_repos())
        return repos

    def get_success_url(self):
        messages.success(
            self.request,
            f"Successfully registered {self.object.name} webapp",
        )
        return reverse_lazy("list-apps")

    def form_valid(self, form):
        repo_url = form.cleaned_data["repo_url"]
        _, name = repo_url.rsplit("/", 1)
        self.object = App.objects.create(
            name=name,
            repo_url=repo_url,
        )
        if form.cleaned_data.get("new_datasource_name"):
            bucket = S3Bucket.objects.create(
                name=form.cleaned_data["new_datasource_name"],
            )
            AppS3Bucket.objects.create(
                app=self.object,
                s3bucket=bucket,
                access_level='readonly',
            )
            UserS3Bucket.objects.create(
                user=self.request.user,
                s3bucket=bucket,
                access_level='readwrite',
                is_admin=True,
            )
        elif form.cleaned_data.get("existing_datasource_id"):
            AppS3Bucket.objects.create(
                app=self.object,
                s3bucket=form.cleaned_data["existing_datasource_id"],
                access_level='readonly',
            )
        UserApp.objects.create(
            app=self.object,
            user=self.request.user,
            is_admin=True,
        )
        return FormMixin.form_valid(self, form)


class GrantAppAccess(LoginRequiredMixin, CreateView):
    form_class = GrantAppAccessForm
    model = AppS3Bucket

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        if "app" not in kwargs:
            kwargs["app"] = App.objects.get(pk=self.kwargs['pk'])
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Successfully granted access")
        return reverse_lazy("manage-app", kwargs={"pk": self.object.app.id})

    def form_valid(self, form):
        try:
            self.object = AppS3Bucket.objects.get(
                s3bucket=form.cleaned_data['datasource'],
                app_id=self.kwargs['pk'],
            )
            self.object.access_level = form.cleaned_data['access_level']
            self.object.save()
        except AppS3Bucket.DoesNotExist:
            self.object = AppS3Bucket.objects.create(
                access_level=form.cleaned_data['access_level'],
                app_id=self.kwargs['pk'],
                s3bucket=form.cleaned_data['datasource'],
            )
        return FormMixin.form_valid(self, form)

    def form_invalid(self, form):
        raise Exception(form.errors)


class RevokeAppAccess(LoginRequiredMixin, DeleteView):
    model = AppS3Bucket

    def get_success_url(self):
        messages.success(self.request, "Successfully disconnected data source")
        return reverse_lazy("manage-app", kwargs={"pk": self.object.app.id})


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
