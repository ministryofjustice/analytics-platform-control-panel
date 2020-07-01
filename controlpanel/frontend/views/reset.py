from django.conf import settings
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import FormView
from controlpanel.frontend.forms import ResetHomeDirectoryForm
import requests


class Reset(LoginRequiredMixin, FormView):
    template_name = "reset.html"
    form_class = ResetHomeDirectoryForm

    def get_success_url(self):
        messages.success(
            self.request,
            "Reset of home directory underway.",
        )
        return reverse_lazy("list-tools")

    def form_valid(self, form):
        """
        Called if the form is valid.

        Kick off the reset of the home directory.
        """
        print("RESET")
        return super().form_valid(form)
