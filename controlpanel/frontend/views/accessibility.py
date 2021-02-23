from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView


class Accessibility(LoginRequiredMixin, TemplateView):
    template_name = "a11y.html"
