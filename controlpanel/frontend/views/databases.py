# Third-party
import structlog
from django.conf import settings
from django.contrib import messages
from django.http.response import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.aws import AWSGlue, AWSLakeFormation, iam_arn
from controlpanel.api.models.user import User
from controlpanel.frontend.forms import TableGrantAccessForm
from controlpanel.oidc import OIDCLoginRequiredMixin

log = structlog.getLogger(__name__)


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

        if context_data["table"]["IsRegisteredWithLakeFormation"]:
            permissions = self._get_permissions(database_name=database_name, table_name=table_name)
            context_data["permissions"] = permissions

        return context_data

    def _get_permissions(self, database_name, table_name):
        lake_formation = AWSLakeFormation()
        result = []

        permissions = lake_formation.list_permissions(
            database_name=database_name, table_name=table_name
        )

        for permission in permissions["PrincipalResourcePermissions"]:
            principal = permission["Principal"]["DataLakePrincipalIdentifier"]
            if "iam" in principal and "_user_" in principal:
                permissions_dict = {
                    "principal": principal,
                    "user": self.get_user_from_arn(principal, "_"),
                    "permissions": permission["Permissions"],
                }

                result.append(permissions_dict)

        return result

    def get_user_from_arn(self, arn, separator):
        return arn.rsplit(separator, 1)[1]


class TableGrantView(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    FormView,
):
    template_name = "table-access-grant.html"
    permission_required = "api.is_superuser"
    form_class = TableGrantAccessForm

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        db_name = self.kwargs["dbname"]
        table_name = self.kwargs["tablename"]
        context_data["dbname"] = db_name
        context_data["tablename"] = table_name
        context_data["entity_type"] = "user"
        context_data["entity_options"] = User.objects.exclude(auth0_id__isnull=True)
        context_data["grant_url"] = f"databases/{db_name}/{table_name}/grant/"

        return context_data


class RevokeTableAccessView(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    View,
):
    permission_required = "api.is_superuser"

    def post(self, request, *args, **kwargs):

        try:
            lake_formation = AWSLakeFormation()
            glue = AWSGlue()
            database_name = kwargs["dbname"]
            table_name = kwargs["tablename"]
            principal_arn = iam_arn(f'role/{settings.ENV}_user_{kwargs["user"]}')

            table_data = glue.get_table(database_name=database_name, table_name=table_name)
            remote_catalog_id = table_data["Table"]["TargetTable"]["CatalogId"]
            remote_database_name = table_data["Table"]["TargetTable"]["DatabaseName"]
            remote_table_name = table_data["Table"]["TargetTable"]["Name"]

            resource_link_permissions = self._get_resource_permissions(
                lake_formation, database_name, table_name, principal_arn
            )

            table_permissions = self._get_resource_permissions(
                lake_formation,
                remote_database_name,
                remote_table_name,
                principal_arn,
                remote_catalog_id,
            )

            # Revoke access to resource link and linked table here
            if resource_link_permissions:
                lake_formation.revoke_table_permission(
                    database_name=database_name,
                    table_name=table_name,
                    principal_arn=principal_arn,
                    permissions=resource_link_permissions,
                )
            if table_permissions:
                lake_formation.revoke_table_permission(
                    database_name=remote_database_name,
                    table_name=remote_table_name,
                    principal_arn=principal_arn,
                    catalog_id=remote_catalog_id,
                    permissions=table_permissions,
                )

            messages.success(self.request, f"Successfully revoked access for user {kwargs['user']}")
            return HttpResponseRedirect(
                reverse_lazy(
                    "manage-table", kwargs={"dbname": database_name, "tablename": table_name}
                )
            )
        except Exception as e:
            log.error(f"Could not revoke access for user {kwargs['user']}", error=str(e))
            messages.error(self.request, f"Could not revoke access for user {kwargs['user']}")
            return HttpResponseRedirect(
                reverse_lazy(
                    "manage-table", kwargs={"dbname": database_name, "tablename": table_name}
                )
            )

    def _get_resource_permissions(
        self, lake_formation, database_name, table_name, principal_arn, catalog_id=None
    ):
        permissions = lake_formation.list_permissions(
            database_name=database_name,
            table_name=table_name,
            principal_arn=principal_arn,
            catalog_id=catalog_id,
        )["PrincipalResourcePermissions"]

        if len(permissions) == 1:
            return permissions[0]["Permissions"]

        if len(permissions) > 1:
            result = []
            for permission in permissions:
                result = result + permission["Permissions"]

            return result

        return None
