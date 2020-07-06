from django.conf import settings
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import FormView
from controlpanel.frontend.forms import ResetHomeDirectoryForm
from controlpanel.frontend.consumers import start_background_task


class Reset(LoginRequiredMixin, FormView):
    """
    A view to help automate the resetting of the user's home directory. To be
    used when, for example, their conda or r-studio deployment gets into a bad
    state. See the related helm chart (TBD) for the details of what actually
    happens in the user's home directory.
    """

    template_name = "reset.html"
    form_class = ResetHomeDirectoryForm

    def get_success_url(self):
        """
        The form is valid, so kick off the background job to run the helm
        chart and signal to the user the reset is underway.
        """
        start_background_task(
            "home.reset",
            {
                "user_id": self.request.user.id,
            },
        )

        messages.success(
            self.request,
            "Home directory reset started. This will take several minutes.",
        )
        return reverse_lazy("list-tools")
