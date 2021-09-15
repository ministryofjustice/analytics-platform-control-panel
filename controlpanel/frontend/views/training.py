from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView


class Training(LoginRequiredMixin, TemplateView):
    template_name = "training.html"
