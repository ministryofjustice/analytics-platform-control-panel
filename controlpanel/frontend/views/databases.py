# Third-party
import botocore
import sentry_sdk
import structlog
from django.conf import settings
from django.contrib import messages
from django.http.response import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import TemplateView, View
from django.views.generic.base import ContextMixin
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
    permission_required = "api.is_database_admin"

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data["databases"] = self._get_database_list(settings.DPR_DATABASE_NAME)
        return context_data

    def _get_database_list(self, database_name=None):
        glue = AWSGlue()

        if not database_name:
            database_data = glue.get_databases()
            return database_data["DatabaseList"]

        result = []
        database_data = glue.get_database(database_name=database_name)
        result.append(database_data["Database"])
        return result


class TablesListView(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "tables-list.html"
    permission_required = "api.is_database_admin"

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        database_name = kwargs["dbname"]

        glue = AWSGlue()

        tables_data = glue.get_tables(database_name=database_name)
        context_data["tables"] = tables_data["TableList"]

        return context_data


class GetTableDataMixin(ContextMixin):

    @property
    def base_table_data(self):
        return {
            "database_name": self.kwargs["dbname"],
            "table_name": self.kwargs["tablename"],
            "region": settings.AWS_DEFAULT_REGION,
            "catalog_id": settings.AWS_DATA_ACCOUNT_ID,
        }

    def get_table_data(self):
        table_data = self.base_table_data.copy()
        # check if the db is a resource link to ensurewe use the correct details when getting table
        glue = AWSGlue()
        database = glue.get_database(database_name=self.kwargs["dbname"])["Database"]
        if "TargetDatabase" in database:
            table_data.update(
                {
                    "database_name": database["TargetDatabase"]["DatabaseName"],
                    "region": database["TargetDatabase"]["Region"],
                    "catalog_id": database["TargetDatabase"]["CatalogId"],
                }
            )
            glue = AWSGlue(region_name=database["TargetDatabase"]["Region"])

        table = glue.get_table(
            database_name=table_data["database_name"],
            table_name=self.kwargs["tablename"],
            catalog_id=table_data["catalog_id"],
        )["Table"]
        table_data["is_registered_with_lake_formation"] = table.get("IsRegisteredWithLakeFormation")
        # check if the table a resource link and update table data with the correct details
        if "TargetTable" in table:
            table_data.update(
                {
                    "database_name": table["TargetTable"]["DatabaseName"],
                    "table_name": table["TargetTable"]["Name"],
                    "region": table["TargetTable"]["Region"],
                    "catalog_id": table["TargetTable"]["CatalogId"],
                }
            )
        return table_data


class ManageTable(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    GetTableDataMixin,
    TemplateView,
):
    template_name = "table-detail.html"
    permission_required = "api.is_database_admin"

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        table_data = self.get_table_data()
        context_data["table"] = table_data

        if not table_data["is_registered_with_lake_formation"]:
            return context_data

        context_data["permissions"] = self._get_permissions(
            database_name=table_data["database_name"],
            table_name=table_data["table_name"],
            region_name=table_data["region"],
            catalog_id=table_data["catalog_id"],
        )
        return context_data

    def _get_permissions(self, database_name, table_name, region_name=None, catalog_id=None):

        region_name = region_name
        lake_formation = AWSLakeFormation(region_name=region_name)
        result = []

        permissions = lake_formation.list_permissions(
            database_name=database_name, table_name=table_name, catalog_id=catalog_id
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
    GetTableDataMixin,
    FormView,
):
    template_name = "table-access-grant.html"
    permission_required = "api.is_database_admin"
    form_class = TableGrantAccessForm

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        db_name = self.kwargs["dbname"]
        table_name = self.kwargs["tablename"]
        context_data["dbname"] = db_name
        context_data["tablename"] = table_name
        context_data["entity_options"] = User.objects.exclude(auth0_id__isnull=True)
        context_data["grant_url"] = reverse(
            viewname="grant-table-permissions", kwargs={"dbname": db_name, "tablename": table_name}
        )

        return context_data

    def get_success_url(self):
        db_name = self.kwargs["dbname"]
        table_name = self.kwargs["tablename"]
        return reverse(viewname="manage-table", kwargs={"dbname": db_name, "tablename": table_name})

    def form_valid(self, form):

        user = form.cleaned_data["user"]
        permissions = form.cleaned_data["access_level"]
        user_arn = iam_arn(f"role/{user.iam_role_name}")

        table_data = self.get_table_data()

        # only grants access on the shared table, not the resource link
        try:
            lake_formation = AWSLakeFormation(region_name=table_data["region"])
            lake_formation.grant_table_permission(
                database_name=table_data["database_name"],
                table_name=table_data["table_name"],
                catalog_id=table_data["catalog_id"],
                permissions=permissions["table"],
                principal_arn=user_arn,
            )
        except botocore.exceptions.ClientError as e:
            messages.error(self.request, f"Could not grant access for user {user.username}")
            sentry_sdk.capture_exception(e)
            return super().form_invalid(form)

        messages.success(self.request, f"Successfully granted access for user {user.username}")
        return super().form_valid(form)


class RevokeTableAccessView(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    GetTableDataMixin,
    View,
):
    permission_required = "api.is_database_admin"

    def post(self, request, *args, **kwargs):
        table_data = self.get_table_data()
        lake_formation = AWSLakeFormation(region_name=table_data["region"])
        principal_arn = iam_arn(f'role/{settings.ENV}_user_{kwargs["user"]}')

        try:
            # only revokes access on the shared table, not the resource link
            lake_formation.revoke_table_permission(
                database_name=table_data["database_name"],
                table_name=table_data["table_name"],
                principal_arn=principal_arn,
                catalog_id=table_data["catalog_id"],
                permissions=["SELECT"],
            )
            messages.success(self.request, f"Successfully revoked access for user {kwargs['user']}")
        except botocore.exceptions.ClientError as e:
            sentry_sdk.capture_exception(e)
            messages.error(self.request, f"Could not revoke access for user {kwargs['user']}")

        return HttpResponseRedirect(
            reverse(
                "manage-table",
                kwargs={"dbname": self.kwargs["dbname"], "tablename": self.kwargs["tablename"]},
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
