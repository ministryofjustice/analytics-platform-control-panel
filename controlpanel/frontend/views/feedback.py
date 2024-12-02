# Third-party
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, FormMixin

# First-party/Local
from controlpanel.api.models import Feedback
from controlpanel.frontend.forms import FeedbackForm
from controlpanel.oidc import OIDCLoginRequiredMixin


class CreateFeedback(OIDCLoginRequiredMixin, CreateView):
    form_class = FeedbackForm
    model = Feedback
    template_name = "feedback-create.html"

    def get_success_url(self):
        return reverse_lazy("feedback-thanks")

    def form_valid(self, form):
        form.save()
        return FormMixin.form_valid(self, form)


class FeedbackThanks(OIDCLoginRequiredMixin, TemplateView):
    template_name = "feedback-thanks.html"
