from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormMixin, DeleteView, UpdateView
from rules.contrib.views import PermissionRequiredMixin

from controlpanel.api.aws import aws
from controlpanel.api.models import IAMManagedPolicy, User
from controlpanel.api.permissions import is_superuser
from controlpanel.frontend.forms import CreateIAMManagedPolicyForm, AddUserToIAMManagedPolicyForm


class IAMManagedPolicyList(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = 'policies'
    model = IAMManagedPolicy
    permission_required = 'api.list_policy'
    template_name = "policy-list.html"

    def get_queryset(self):
        return IAMManagedPolicy.objects.filter(created_by=self.request.user)


class AdminIAMManagedPolicyList(IAMManagedPolicyList):
    permission_required = 'api.is_superuser'

    def get_queryset(self):
        return IAMManagedPolicy.objects.all()


class IAMManagedPolicyCreate(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    form_class = CreateIAMManagedPolicyForm
    model = IAMManagedPolicy
    permission_required = 'api.create_policy'
    template_name = "policy-create.html"

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_success_url(self):
        return reverse_lazy("list-policies")

    def form_valid(self, form):
        self.object = IAMManagedPolicy(
            name=form.cleaned_data['name'],
            created_by=self.request.user
        )
        self.object.save()
        messages.success(
            self.request,
            f"Successfully created {self.object.name} policy",
        )
        return FormMixin.form_valid(self, form)



class IAMManagedPolicyDetail(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    form_class = AddUserToIAMManagedPolicyForm
    model = IAMManagedPolicy
    permission_required = 'api.create_policy'
    template_name = "policy-update.html"

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_options = User.objects.exclude(
            pk__in=self.object.users.values_list('auth0_id', flat=True)
        )
        context.update({
            "users_options": user_options
        })
        return context

    def get_success_url(self):
        return reverse_lazy(
                "manage-policy",
                kwargs={"pk": self.object.id}
            )

    def form_valid(self, form):
        user_id = form.cleaned_data['user_id']
        user = User.objects.get(pk=user_id)
        self.object.users.add(user)
        self.object.save()
        messages.success(
            self.request,
            f"Successfully added user {user.name} ",
        )
        return FormMixin.form_valid(self, form)


class IAMManagedPolicyDelete(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = IAMManagedPolicy
    permission_required = 'api.destroy_policy'

    def get_success_url(self):
        messages.success(self.request, "Successfully delete data source")
        return reverse_lazy("list-policies")

    def get_queryset(self):
        queryset = IAMManagedPolicy.objects.all()
        if is_superuser(self.request.user):
            return queryset
        return queryset.filter(created_by=self.request.user)


class IAMManagedPolicyFormRoleList(LoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        roles = aws.list_role_names()
        data = [
            r for r in roles
            if r.startswith(f"airflow")
            or r.startswith(f"{settings.ENV}_app")
        ]
        return JsonResponse(data, safe=False)


class IAMManagedPolicyRemoveUser(LoginRequiredMixin, PermissionRequiredMixin, SingleObjectMixin, View):
    model = IAMManagedPolicy
    permission_required = 'api.update_policy'

    def get_success_url(self):
        messages.success(self.request, "Successfully removed user")
        return reverse_lazy("manage-policy", kwargs={"pk": self.object.id})

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        user = User.objects.get(pk=kwargs['user_id'])
        self.object.users.remove(user)
        return HttpResponseRedirect(self.get_success_url())
