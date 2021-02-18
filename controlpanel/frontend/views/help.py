from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView


class Help(LoginRequiredMixin, TemplateView):
    template_name = "help.html"
