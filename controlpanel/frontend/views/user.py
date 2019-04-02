from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from controlpanel.api.models import User


class UserList(LoginRequiredMixin, ListView):
    model = User
    template_name = "user-list.html"


class UserDetail(LoginRequiredMixin, DetailView):
    model = User
    template_name = "user-detail.html"
