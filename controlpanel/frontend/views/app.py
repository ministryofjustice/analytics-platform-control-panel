import re

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.template.defaultfilters import pluralize
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import (
    CreateView,
    DeleteView,
    FormMixin,
    UpdateView,
)
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin
import sentry_sdk

from controlpanel.api.cluster import get_repositories
from controlpanel.api import cluster
from controlpanel.api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
    User,
    UserApp,
    UserS3Bucket,
)
from controlpanel.frontend.forms import (
    AddAppCustomersForm,
    CreateAppForm,
    GrantAppAccessForm,
)


class AppList(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = 'apps'
    model = App
    permission_required = 'api.list_app'
    template_name = "webapp-list.html"

    def get_queryset(self):
        qs = App.objects.all().prefetch_related('userapps')
        return qs.filter(userapps__user=self.request.user)


class AdminAppList(AppList):
    permission_required = 'api.is_superuser'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['all_webapps'] = True
        return context

    def get_queryset(self):
        return App.objects.all().prefetch_related('userapps')


class AppDetail(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    context_object_name = 'app'
    model = App
    permission_required = 'api.retrieve_app'
    template_name = "webapp-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app = self.get_object()

        context["app_url"] = cluster.App(app).url
        context["admin_options"] = User.objects.filter(
            auth0_id__isnull=False,
        ).exclude(
            auth0_id='',
        ).exclude(
            auth0_id__in=[user.auth0_id for user in app.admins],
        )

        context["grant_access_form"] = GrantAppAccessForm(
            app=app,
            exclude_connected=True,
        )

        add_customer_form_errors = self.request.session.pop('add_customer_form_errors', None)
        if add_customer_form_errors:
            errors = context.setdefault('errors', {})
            errors['customer_email'] = add_customer_form_errors['customer_email']

        context['kibana_base_url'] = settings.KIBANA_BASE_URL

        return context


class CreateApp(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    form_class = CreateAppForm
    model = App
    permission_required = 'api.create_app'
    template_name = "webapp-create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['repos'] = get_repositories(self.request.user)
        return context

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        kwargs.update(request=self.request)
        return kwargs

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


class GrantAppAccess(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    CreateView,
):
    form_class = GrantAppAccessForm
    model = AppS3Bucket
    permission_required = 'api.add_app_bucket'

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        if "app" not in kwargs:
            kwargs["app"] = App.objects.get(pk=self.kwargs['pk'])
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Successfully granted access")
        return reverse_lazy("manage-app", kwargs={"pk": self.object.app.id})

    def form_valid(self, form):
        # TODO this can be replaced with AppS3Bucket.objects.get_or_create()
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
        # It should be impossible to get here. The form consists of
        # ChoiceFields, so the only way an invalid input can be submitted is by
        # constructing the request manually - in which (suspicious) case we should
        # return as little information as possible
        log.warning('Received suspicious invalid grant app access request')
        raise Exception(form.errors)


class RevokeAppAccess(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = AppS3Bucket
    permission_required = 'api.remove_app_bucket'

    def get_success_url(self):
        messages.success(self.request, "Successfully disconnected data source")
        return reverse_lazy("manage-app", kwargs={"pk": self.object.app.id})


class UpdateAppAccess(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = AppS3Bucket
    permission_required = 'api.update_apps3bucket'
    fields = ['access_level']

    def get_success_url(self):
        messages.success(self.request, "Successfully updated access")
        if self.request.POST.get('return_to') == 'manage-datasource':
            return reverse_lazy('manage-datasource', kwargs={'pk': self.object.s3bucket.id})
        return reverse_lazy("manage-app", kwargs={"pk": self.object.app.id})


class DeleteApp(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = App
    permission_required = 'api.destroy_app'
    success_url = reverse_lazy("list-apps")

    def delete(self, request, *args, **kwargs):
        app = self.get_object()
        messages.success(self.request, f"Successfully deleted {app.name} app")
        return super().delete(request, *args, **kwargs)


class UpdateApp(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    SingleObjectMixin,
    RedirectView,
):
    http_method_names = ['post']
    model = App

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("manage-app", kwargs={'pk': kwargs['pk']})

    def post(self, request, *args, **kwargs):
        self.perform_update(**kwargs)
        return super().post(request, *args, **kwargs)


class AddCustomers(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    form_class = AddAppCustomersForm
    model = App
    permission_required = 'api.add_app_customer'

    def form_invalid(self, form):
        self.request.session['add_customer_form_errors'] = form.errors
        return HttpResponseRedirect(
            reverse_lazy("manage-app", kwargs={"pk": self.kwargs['pk']}),
        )

    def form_valid(self, form):
        self.get_object().add_customers(form.cleaned_data['customer_email'])
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        return kwargs

    def get_success_url(self, *args, **kwargs):
        messages.success(self.request, f"Successfully added customers")
        return reverse_lazy("manage-app", kwargs={"pk": self.kwargs["pk"]})


class RemoveCustomer(UpdateApp):
    permission_required = 'api.remove_app_customer'

    def perform_update(self, **kwargs):
        app = self.get_object()
        user_ids = self.request.POST.getlist('customer')
        try:
            app.delete_customers(user_ids)
        except App.DeleteCustomerError as e:
            sentry_sdk.capture_exception(e)
            messages.error(self.request, f"Failed removing customer{pluralize(user_ids)}")
        else:
            messages.success(self.request, f"Successfully removed customer{pluralize(user_ids)}")


class AddAdmin(UpdateApp):
    permission_required = 'api.add_app_admin'

    def perform_update(self, **kwargs):
        app = self.get_object()
        user = get_object_or_404(User, pk=self.request.POST['user_id'])
        userapp = UserApp.objects.create(
            app=app,
            user=user,
            is_admin=True,
        )
        userapp.save()
        messages.success(self.request, f"Granted admin access to {user.name}")


class RevokeAdmin(UpdateApp):
    permission_required = 'api.revoke_app_admin'

    def perform_update(self, **kwargs):
        app = self.get_object()
        user = get_object_or_404(User, pk=kwargs['user_id'])
        userapp = get_object_or_404(UserApp, app=app, user=user)
        userapp.delete()
        messages.success(self.request, f"Revoked admin access for {user.name}")

