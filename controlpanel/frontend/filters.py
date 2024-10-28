# Third-party
import django_filters

# First-party/Local
from controlpanel.api.models.tool import Tool


class ReleaseFilter(django_filters.FilterSet):
    chart_name = django_filters.ChoiceFilter()
    is_restricted = django_filters.BooleanFilter(label="Restricted release?")

    class Meta:
        model = Tool
        fields = ["chart_name", "is_restricted"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["chart_name"].extra["choices"] = Tool.objects.values_list(
            "chart_name", "chart_name"
        ).distinct()
        self.filters["chart_name"].field.widget.attrs = {"class": "govuk-select"}
        self.filters["is_restricted"].field.widget.choices = [
            ("all", "All"),
            ("true", "Yes"),
            ("false", "No"),
        ]
        self.filters["is_restricted"].field.widget.attrs = {"class": "govuk-select"}
