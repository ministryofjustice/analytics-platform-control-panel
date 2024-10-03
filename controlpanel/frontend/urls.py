# Third-party
from django.urls import path

# First-party/Local
from controlpanel.frontend import views
from controlpanel.frontend.views import app_variables, secrets

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("oidc/entraid/auth/", views.EntraIdAuthView.as_view(), name="entraid-auth"),
    path("oidc/logout/", views.LogoutView.as_view(), name="oidc_logout"),
    path("datasources/", views.AdminBucketList.as_view(), name="list-all-datasources"),
    path("datasources/<int:pk>/", views.BucketDetail.as_view(), name="manage-datasource"),
    path(
        "datasources/<int:pk>/access/",
        views.GrantAccess.as_view(),
        name="grant-datasource-access",
    ),
    path(
        "datasources/<int:pk>/delete/",
        views.DeleteDatasource.as_view(),
        name="delete-datasource",
    ),
    path("datasources/new/", views.CreateDatasource.as_view(), name="create-datasource"),
    path(
        "datasource-access/<int:pk>/",
        views.UpdateAccessLevel.as_view(),
        name="update-access-level",
    ),
    path(
        "datasource-access/<int:pk>/delete/",
        views.RevokeAccess.as_view(),
        name="revoke-datasource-access",
    ),
    path("groups/", views.IAMManagedPolicyList.as_view(), name="list-policies"),
    path(
        "groups/all/",
        views.AdminIAMManagedPolicyList.as_view(),
        name="list-all-policies",
    ),
    path("groups/new/", views.IAMManagedPolicyCreate.as_view(), name="create-policy"),
    path(
        "groups/<int:pk>/delete/",
        views.IAMManagedPolicyDelete.as_view(),
        name="delete-policy",
    ),
    path("groups/<int:pk>/", views.IAMManagedPolicyDetail.as_view(), name="manage-policy"),
    path(
        "groups/<int:pk>/user/<str:user_id>/delete/",
        views.IAMManagedPolicyRemoveUser.as_view(),
        name="policy-remove-user",
    ),
    path(
        "datasources/<int:pk>/update-group-access/",
        views.UpdateIAMManagedPolicyAccessLevel.as_view(),
        name="update-policy-access-level",
    ),
    path(
        "datasources/<int:pk>/delete-group-access/",
        views.RevokeIAMManagedPolicyAccess.as_view(),
        name="revoke-datasource-policy-access",
    ),
    path(
        "datasources/<int:pk>/group-access/",
        views.GrantPolicyAccess.as_view(),
        name="grant-datasource-policy-access",
    ),
    path("tools/", views.ToolList.as_view(), name="list-tools"),
    path(
        "tools/<str:name>/restart/<str:tool_id>",
        views.RestartTool.as_view(),
        name="restart-tool",
    ),
    path("users/", views.UserList.as_view(), name="list-users"),
    path("users/<str:pk>/", views.UserDetail.as_view(), name="manage-user"),
    path("users/<str:pk>/delete/", views.UserDelete.as_view(), name="delete-user"),
    path("users/<str:pk>/bedrock/", views.EnableBedrockUser.as_view(), name="set-bedrock-user"),
    path("users/<str:pk>/quicksight/", views.SetQuicksightAccess.as_view(), name="set-quicksight"),
    path(
        "users/<str:pk>/database-admin/",
        views.EnableDatabaseAdmin.as_view(),
        name="set-database-admin",
    ),
    path("users/<str:pk>/edit/", views.SetSuperadmin.as_view(), name="set-superadmin"),
    path("users/<str:pk>/reset-mfa/", views.ResetMFA.as_view(), name="reset-mfa"),
    path("warehouse-data/", views.BucketList.as_view(), name="list-warehouse-datasources"),
    path("webapp-data/", views.WebappBucketList.as_view(), name="list-webapp-datasources"),
    path("webapps/", views.AppList.as_view(), name="list-apps"),
    path("webapps/all/", views.AdminAppList.as_view(), name="list-all-apps"),
    path("webapps/new/", views.CreateApp.as_view(), name="create-app"),
    path("webapps/<int:pk>/", views.AppDetail.as_view(), name="manage-app"),
    path("webapps/<int:pk>/delete/", views.DeleteApp.as_view(), name="delete-app"),
    path(
        "webapps/<int:pk>/create_auth0_client/",
        views.SetupAppAuth0.as_view(),
        name="create-auth0-client",
    ),
    path(
        "webapps/<int:pk>/remove_auth0_client/",
        views.RemoveAppAuth0.as_view(),
        name="remove-auth0-client",
    ),
    path(
        "webapps/<int:pk>/update_auth0_connections/",
        views.UpdateAppAuth0Connections.as_view(),
        name="update-auth0-connections",
    ),
    path(
        "webapps/<int:pk>/remove_app_deployment_env/<str:env_name>",
        views.RemoveAppDeploymentEnv.as_view(),
        name="remove-app-deployment-env",
    ),
    path(
        "webapps/<int:pk>/groups/<uuid:group_id>/customers/add/",
        views.AddCustomers.as_view(),
        name="add-app-customers",
    ),
    path(
        "webapps/<int:pk>/groups/<uuid:group_id>/customers/remove/",
        views.RemoveCustomer.as_view(),
        name="remove-app-customer",
    ),
    path(
        "webapps/<int:pk>/groups/<uuid:group_id>/customers/remove/email/",
        views.RemoveCustomerByEmail.as_view(),
        name="remove-app-customer-by-email",
    ),
    path(
        "apps/<int:pk>/customers/paginate/<int:page_no>/",
        views.app.AppCustomersPageView.as_view(),
        name="appcustomers-page",
    ),
    path("webapps/<int:pk>/admins/", views.AddAdmin.as_view(), name="add-app-admin"),
    path(
        "webapps/<int:pk>/admins/<str:user_id>/revoke/",
        views.RevokeAdmin.as_view(),
        name="revoke-app-admin",
    ),
    path(
        "webapps/<int:pk>/datasource-access/",
        views.GrantAppAccess.as_view(),
        name="grant-app-access",
    ),
    path(
        "webapps/<int:pk>/secrets/add",
        secrets.AppSecretCreate.as_view(),
        name="create-app-secret",
    ),
    path(
        "webapps/<int:pk>/secrets/<str:secret_name>/update/",
        secrets.AppSecretUpdate.as_view(),
        name="update-app-secret",
    ),
    path(
        "webapps/<int:pk>/secrets/<str:secret_name>/delete/",
        secrets.AppSecretDelete.as_view(),
        name="delete-app-secret",
    ),
    path(
        "webapps/<int:pk>/vars/add",
        app_variables.AppVariableCreate.as_view(),
        name="create-app-var",
    ),
    path(
        "webapps/<int:pk>/vars/<str:var_name>/update/",
        app_variables.AppVariableUpdate.as_view(),
        name="update-app-var",
    ),
    path(
        "webapps/<int:pk>/vars/<str:var_name>/delete/",
        app_variables.AppVariableDelete.as_view(),
        name="delete-app-var",
    ),
    path(
        "webapps/<int:pk>/bedrock/",
        views.EnableBedrockApp.as_view(),
        name="set-bedrock-app",
    ),
    path(
        "webapps/<int:pk>/textract/",
        views.EnableTextractApp.as_view(),
        name="set-textract-app",
    ),
    path(
        "webapps/<int:pk>/update-ip-allowlists/",
        views.UpdateAppIPAllowlists.as_view(),
        name="update-app-ip-allowlists",
    ),
    path(
        "webapp-datasource-access/<int:pk>/",
        views.UpdateAppAccess.as_view(),
        name="update-app-access",
    ),
    path(
        "webapp-datasource-access/<int:pk>/delete/",
        views.RevokeAppAccess.as_view(),
        name="revoke-app-access",
    ),
    path("reset-user-home/", views.ResetHome.as_view(), name="home-reset"),
    path("login-fail/", views.LoginFail.as_view(), name="login-fail"),
    path("help/", views.Help.as_view(), name="help"),
    path("releases/", views.ReleaseList.as_view(), name="list-tool-releases"),
    path("release/new/", views.ReleaseCreate.as_view(), name="create-tool-release"),
    path("release/<int:pk>/", views.ReleaseDetail.as_view(), name="manage-tool-release"),
    path(
        "release/<int:pk>/delete/",
        views.ReleaseDelete.as_view(),
        name="delete-tool-release",
    ),
    path("ip-allowlists/", views.IPAllowlistList.as_view(), name="list-ip-allowlists"),
    path(
        "ip-allowlists/new/",
        views.IPAllowlistCreate.as_view(),
        name="create-ip-allowlist",
    ),
    path(
        "ip-allowlists/<int:pk>/",
        views.IPAllowlistDetail.as_view(),
        name="manage-ip-allowlist",
    ),
    path(
        "ip-allowlists/<int:pk>/delete/",
        views.IPAllowlistDelete.as_view(),
        name="delete-ip-allowlist",
    ),
    path("accessibility/", views.Accessibility.as_view(), name="accessibility"),
    path("tasks/", views.TaskList.as_view(), name="list-tasks"),
    path("databases/", views.DatabasesListView.as_view(), name="list-databases"),
    path("databases/<str:dbname>/", views.TablesListView.as_view(), name="list-tables"),
    path(
        "databases/<str:dbname>/<slug:tablename>/grant/",
        views.TableGrantView.as_view(),
        name="grant-table-permissions",
    ),
    path(
        "databases/<str:dbname>/<str:tablename>/<str:user>/revoke/",
        views.RevokeTableAccessView.as_view(),
        name="revoke-table-permissions",
    ),
    path(
        "databases/<str:dbname>/<str:tablename>/",
        views.ManageTable.as_view(),
        name="manage-table",
    ),
]
