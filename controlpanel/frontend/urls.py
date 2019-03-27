from django.urls import path

from controlpanel.frontend import views


urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path(
        "warehouse-data",
        views.WarehouseData.as_view(),
        name="list-warehouse-datasources",
    ),
    path(
        "warehouse-datasource/<int:pk>",
        views.WarehouseBucketDetail.as_view(),
        name="manage-warehouse-datasource",
    ),
    path("webapp-data", views.WebappData.as_view(), name="list-webapp-datasources"),
    path(
        "webapp-datasource/<int:pk>",
        views.WebappBucketDetail.as_view(),
        name="manage-webapp-datasource",
    ),
    path("webapps", views.AppsList.as_view(), name="list-apps"),
    path("webapps/new", views.CreateApp.as_view(), name="create-app"),
    path("webapps/<int:pk>", views.AppDetail.as_view(), name="manage-app"),
    path("webapps/<int:pk>/delete", views.DeleteApp.as_view(), name="delete-app"),
    path(
        "webapps/<int:pk>/customers/add",
        views.AddCustomers.as_view(),
        name="add-app-customers",
    ),
    path(
        "webapps/<int:pk>/customers/remove",
        views.RemoveCustomer.as_view(),
        name="remove-app-customer",
    ),
    path("webapps/<int:pk>/admins", views.AddAdmin.as_view(), name="add-app-admin"),
    path(
        "webapps/<int:pk>/admins/<str:user_id>/revoke",
        views.RevokeAdmin.as_view(),
        name="revoke-app-admin",
    ),
    path("tools", views.ToolsList.as_view(), name="list-tools"),
    path("tools/<str:name>/deploy", views.DeployTool.as_view(), name="deploy-tool"),
    path("tools/<str:name>/restart", views.RestartTool.as_view(), name="restart-tool"),
    path("whats-new", views.WhatsNew.as_view(), name="whats-new"),
]
