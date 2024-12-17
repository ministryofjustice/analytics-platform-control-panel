# Third-party
import django_filters

# First-party/Local
from controlpanel.api.models.tool import Tool


class InitialFilterSetMixin(django_filters.FilterSet):

    def __init__(self, data=None, queryset=None, *, request=None, prefix=None):
        # if filterset is bound, use initial values as defaults
        if data is not None:
            # get a mutable copy of the QueryDict
            data = data.copy()

            for name, f in self.base_filters.items():
                initial = f.extra.get("initial")

                # filter param is either missing or empty, use initial as default
                if not data.get(name) and initial:
                    data[name] = initial

        super().__init__(data, queryset, request=request, prefix=prefix)


class ReleaseFilter(InitialFilterSetMixin):
    YES_NO_CHOICES = [("all", "---------"), ("true", "Yes"), ("false", "No")]
    chart_name = django_filters.ChoiceFilter()
    # is_restricted = django_filters.BooleanFilter(label="Restricted release?")
    status = django_filters.ChoiceFilter(
        choices=[
            (Tool.STATUS_ACTIVE, Tool.STATUS_ACTIVE.capitalize()),
            (Tool.STATUS_RESTRICTED, Tool.STATUS_RESTRICTED.capitalize()),
            (Tool.STATUS_DEPRECATED, Tool.STATUS_DEPRECATED.capitalize()),
            (Tool.STATUS_RETIRED, Tool.STATUS_RETIRED.capitalize()),
            ("all", "All"),
        ],
        method="filter_status",
        label="Status",
        empty_label=None,
        initial="active",
    )

    class Meta:
        model = Tool
        fields = [
            "chart_name",
        ]

    def __init__(self, data=None, *args, **kwargs):
        super().__init__(data, *args, **kwargs)
        self.filters["chart_name"].extra["choices"] = (
            Tool.objects.values_list("chart_name", "chart_name").order_by().distinct()
        )
        self.filters["chart_name"].field.widget.attrs = {"class": "govuk-select"}
        self.filters["status"].field.widget.attrs = {"class": "govuk-select"}

    def filter_status(self, queryset, name, value):
        if value == "all":
            return queryset
        if value == "retired":
            return queryset.filter(is_retired=True)
        # remove retired tools from the list
        queryset = queryset.filter(is_retired=False)
        if value == "active":
            return queryset.filter(is_restricted=False, is_deprecated=False)
        return queryset.filter(
            **{
                f"is_{value}": True,
            }
        )
