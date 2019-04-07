from django.urls import path

from controlpanel.frontend import views


urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("datasources", views.BucketList.as_view(), name="list-all-datasources"),
    path("datasources/<int:pk>", views.BucketDetail.as_view(), name="manage-datasource"),
    path("datasources/<int:pk>/access", views.GrantAccess.as_view(), name="grant-datasource-access"),
    path("datasources/<int:pk>/delete", views.DeleteDatasource.as_view(), name="delete-datasource"),
    path("datasources/new", views.CreateDatasource.as_view(), name="create-datasource"),
    path("datasource-access/<int:pk>", views.UpdateAccessLevel.as_view(), name="update-access-level"),
    path("datasource-access/<int:pk>/delete", views.RevokeAccess.as_view(), name="revoke-datasource-access"),
    path("tools", views.ToolsList.as_view(), name="list-tools"),
    path("tools/<str:name>/deploy", views.DeployTool.as_view(), name="deploy-tool"),
    path("tools/<str:name>/restart", views.RestartTool.as_view(), name="restart-tool"),
    path("users", views.UserList.as_view(), name="list-users"),
    path("users/<str:pk>", views.UserDetail.as_view(), name="manage-user"),
    path("users/<str:pk>/delete", views.UserDelete.as_view(), name="delete-user"),
    path("users/<str:pk>/edit", views.SetSuperadmin.as_view(), name="set-superadmin"),
    path("users/<str:pk>/reset-mfa", views.ResetMFA.as_view(), name="reset-mfa"),
    path("warehouse-data", views.WarehouseData.as_view(), name="list-warehouse-datasources"),
    path("webapp-data", views.WebappData.as_view(), name="list-webapp-datasources"),
    path("webapps", views.AppsList.as_view(), name="list-apps"),
    path("webapps/all", views.AppsList.as_view(all_apps=True), name="list-all-apps"),
    path("webapps/new", views.CreateApp.as_view(), name="create-app"),
    path("webapps/<int:pk>", views.AppDetail.as_view(), name="manage-app"),
    path("webapps/<int:pk>/delete", views.DeleteApp.as_view(), name="delete-app"),
    path("webapps/<int:pk>/customers/add", views.AddCustomers.as_view(), name="add-app-customers"),
    path("webapps/<int:pk>/customers/remove", views.RemoveCustomer.as_view(), name="remove-app-customer"),
    path("webapps/<int:pk>/admins", views.AddAdmin.as_view(), name="add-app-admin"),
    path("webapps/<int:pk>/admins/<str:user_id>/revoke", views.RevokeAdmin.as_view(), name="revoke-app-admin"),
    path("webapps/<int:pk>/datasource-access", views.GrantAppAccess.as_view(), name="grant-app-access"),
    path("webapp-datasource-access/<int:pk>/delete", views.RevokeAppAccess.as_view(), name="revoke-app-access"),
    path("whats-new", views.WhatsNew.as_view(), name="whats-new"),
]
