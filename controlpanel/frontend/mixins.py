# Standard library
import csv
from datetime import datetime

# Third-party
from django.contrib import messages
from django.http import HttpResponse
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.oidc import OIDCLoginRequiredMixin


class PolicyAccessMixin(OIDCLoginRequiredMixin, PermissionRequiredMixin):
    """
    Updates policy access for a model instance.
    Assumes updating a boolean field and updating a policy based on it.
    Must set success_message and method_name attributes on view.
    """

    http_method_names = ["post"]
    permission_required = "api.add_superuser"
    success_message = ""
    method_name = ""

    def form_valid(self, form):
        if not hasattr(self.object, self.method_name):
            raise AttributeError(f"Method {self.method_name} not found on {self.object}")

        getattr(self.object, self.method_name)()
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, self.success_message)
        return super().get_success_url()


class CsvWriterMixin(OIDCLoginRequiredMixin, PermissionRequiredMixin):
    """
    Allows exporting a list of models to a CSV file.
    """

    http_method_names = ["post"]
    permission_required = "api.is_superuser"
    filename = ""
    csv_headings = []
    model_attributes = []

    def write_csv(self, models):
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

        response = HttpResponse(
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{self.filename}_{timestamp}.csv"'
            },
        )

        writer = csv.writer(response)
        writer.writerow(self.csv_headings)
        for model in models:
            row = [model[attribute] for attribute in self.model_attributes]
            writer.writerow(row)

        return response
