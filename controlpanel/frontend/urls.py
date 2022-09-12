from xml.etree.ElementInclude import include
from django.urls import path

from controlpanel.frontend import views
from controlpanel.frontend.views import secrets


urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("oidc/logout/", views.LogoutView.as_view(), name="oidc_logout"),

    path("datasources/", views.AdminBucketList.as_view(), name="list-all-datasources"),
    path("datasources/<int:pk>/", views.BucketDetail.as_view(), name="manage-datasource"),
    path("datasources/<int:pk>/access/", views.GrantAccess.as_view(), name="grant-datasource-access"),
    path("datasources/<int:pk>/delete/", views.DeleteDatasource.as_view(), name="delete-datasource"),
    path("datasources/new/", views.CreateDatasource.as_view(), name="create-datasource"),
    path("datasource-access/<int:pk>/", views.UpdateAccessLevel.as_view(), name="update-access-level"),
    path("datasource-access/<int:pk>/delete/", views.RevokeAccess.as_view(), name="revoke-datasource-access"),

    path("groups/", views.IAMManagedPolicyList.as_view(), name="list-policies"),
    path("groups/all/", views.AdminIAMManagedPolicyList.as_view(), name="list-all-policies"),
    path("groups/new/", views.IAMManagedPolicyCreate.as_view(), name="create-policy"),
    path("groups/<int:pk>/delete/", views.IAMManagedPolicyDelete.as_view(), name="delete-policy"),
    path("groups/<int:pk>/", views.IAMManagedPolicyDetail.as_view(), name="manage-policy"),
    path("groups/<int:pk>/user/<str:user_id>/delete/", views.IAMManagedPolicyRemoveUser.as_view(), name="policy-remove-user"),
    path("datasources/<int:pk>/update-group-access/", views.UpdateIAMManagedPolicyAccessLevel.as_view(), name="update-policy-access-level"),
    path("datasources/<int:pk>/delete-group-access/", views.RevokeIAMManagedPolicyAccess.as_view(), name="revoke-datasource-policy-access"),
    path("datasources/<int:pk>/group-access/", views.GrantPolicyAccess.as_view(), name="grant-datasource-policy-access"),

    path("parameters/", views.ParameterList.as_view(), name="list-parameters"),
    path("parameters/all/", views.AdminParameterList.as_view(), name="list-all-parameters"),
    path("parameters/form/role-list.js", views.ParameterFormRoleList.as_view(), name="parameters-list-roles"),
    path("parameters/new/", views.ParameterCreate.as_view(), name="create-parameter"),
    path("parameters/<int:pk>/delete/", views.ParameterDelete.as_view(), name="delete-parameter"),
    path("tools/", views.ToolList.as_view(), name="list-tools"),
    path("tools/<str:name>/deploy/", views.DeployTool.as_view(), name="deploy-tool"),
    path("tools/<str:name>/restart/", views.RestartTool.as_view(), name="restart-tool"),
    path("users/", views.UserList.as_view(), name="list-users"),
    path("users/<str:pk>/", views.UserDetail.as_view(), name="manage-user"),
    path("users/<str:pk>/delete/", views.UserDelete.as_view(), name="delete-user"),
    path("users/<str:pk>/edit/", views.SetSuperadmin.as_view(), name="set-superadmin"),
    path("users/<str:pk>/reset-mfa/", views.ResetMFA.as_view(), name="reset-mfa"),
    path("warehouse-data/", views.BucketList.as_view(), name="list-warehouse-datasources"),
    path("webapp-data/", views.WebappBucketList.as_view(), name="list-webapp-datasources"),
    path("webapps/", views.AppList.as_view(), name="list-apps"),
    path("webapps/all/", views.AdminAppList.as_view(), name="list-all-apps"),
    path("webapps/new/", views.CreateApp.as_view(), name="create-app"),
    path("webapps/<int:pk>/", views.AppDetail.as_view(), name="manage-app"),
    path("webapps/<int:pk>/delete/", views.DeleteApp.as_view(), name="delete-app"),
    path("webapps/<int:pk>/setup_app_auth0/", views.SetupAppAuth0.as_view(), name="setup-app-auth0"),
    path("webapps/<int:pk>/reset_app_secret/", views.ResetAppSecret.as_view(), name="reset-app-secret"),
    path("webapps/<int:pk>/customers/add/", views.AddCustomers.as_view(), name="add-app-customers"),
    path("webapps/<int:pk>/customers/remove/", views.RemoveCustomer.as_view(), name="remove-app-customer"),
    path("webapps/<int:pk>/admins/", views.AddAdmin.as_view(), name="add-app-admin"),
    path("webapps/<int:pk>/admins/<str:user_id>/revoke/", views.RevokeAdmin.as_view(), name="revoke-app-admin"),
    path("webapps/<int:pk>/datasource-access/", views.GrantAppAccess.as_view(), name="grant-app-access"),

    path('webapps/<int:pk>/secrets/view/', secrets.SecretAddViewSet.as_view(), name='view-secret'),
    path('webapps/<int:pk>/secrets/add/<str:secret_key>/', secrets.SecretAddUpdate.as_view(), name='add-secret'),
    path('webapps/<int:pk>/secrets/delete/<str:secret_key>/', secrets.SecretDelete.as_view(), name='delete-secret'),

    path("webapp-datasource-access/<int:pk>/", views.UpdateAppAccess.as_view(), name="update-app-access"),
    path("webapp-datasource-access/<int:pk>/delete/", views.RevokeAppAccess.as_view(), name="revoke-app-access"),
    path("reset-user-home/", views.ResetHome.as_view(), name="home-reset"),
    path("login-fail/", views.LoginFail.as_view(), name="login-fail"),
    path("help/", views.Help.as_view(), name="help"),
    path("releases/", views.ReleaseList.as_view(), name="list-tool-releases"),
    path("release/new/", views.ReleaseCreate.as_view(), name="create-tool-release"),
    path("release/<int:pk>/", views.ReleaseDetail.as_view(), name="manage-tool-release"),
    path("release/<int:pk>/delete/", views.ReleaseDelete.as_view(), name="delete-tool-release"),
    path("accessibility/", views.Accessibility.as_view(), name="accessibility"),
]
