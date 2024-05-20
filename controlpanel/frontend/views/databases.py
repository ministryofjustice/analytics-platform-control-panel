# Third-party
from django.views.generic import TemplateView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.aws import AWSGlue
from controlpanel.oidc import OIDCLoginRequiredMixin


class DatabasesListView(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "databases-list.html"
    permission_required = "api.is_superuser"

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)

        glue = AWSGlue()

        database_data = glue.get_databases()
        context_data["databases"] = database_data["DatabaseList"]

        return context_data


class TablesListView(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "tables-list.html"
    permission_required = "api.is_superuser"

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        database_name = kwargs["dbname"]

        glue = AWSGlue()

        tables_data = glue.get_tables(database_name=database_name)
        context_data["tables"] = tables_data["TableList"]

        return context_data


class ManageTable(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "table-detail.html"
    permission_required = "api.is_superuser"

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        database_name = kwargs["dbname"]
        table_name = kwargs["tablename"]

        glue = AWSGlue()

        tables_data = glue.get_table(database_name=database_name, table_name=table_name)
        context_data["table"] = tables_data["Table"]

        return context_data
