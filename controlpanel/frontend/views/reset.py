# Third-party
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic.edit import FormView

# First-party/Local
from controlpanel.frontend.forms import ResetHomeDirectoryForm
from controlpanel.oidc import OIDCLoginRequiredMixin
from controlpanel.utils import start_background_task


class ResetHome(OIDCLoginRequiredMixin, FormView):
    """
    A view to help automate the resetting of the user's home directory. To be
    used when, for example, their conda or r-studio deployment gets into a bad
    state. See the related reset-user-home helm chart for the details of what
    actually happens in the user's home directory:
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
            "Home directory reset. Wait a few seconds and restart RStudio.",
        )
        return reverse_lazy("list-tools")
