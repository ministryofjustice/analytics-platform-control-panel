# Third-party
from django.urls import include, path
from rest_framework import routers

# First-party/Local
from controlpanel.api import views

router = routers.DefaultRouter()
router.register("apps", views.AppViewSet, basename='app')
router.register("apps/app_name", views.AppByNameViewSet, basename="apps-by-name")
router.register("apps3buckets", views.AppS3BucketViewSet)
router.register("s3buckets", views.S3BucketViewSet)
router.register("tools", views.ToolViewSet, basename="tool")
router.register("userapps", views.UserAppViewSet)
router.register("users", views.UserViewSet)
router.register("users3buckets", views.UserS3BucketViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("repos/<str:org_name>/", views.repos.RepoApi.as_view(), name="github-repos"),
    path("repos/<str:org_name>/<str:repo_name>/environments",
         views.repos.RepoEnvironmentAPI.as_view(),
         name="github-repo-env"),
    path(
        "apps/<uuid:res_id>/customers/",
        views.AppCustomersAPIView.as_view(),
        name="appcustomers-list",
    ),
    path(
        "apps/<uuid:res_id>/customers/<str:user_id>/",
        views.AppCustomersDetailAPIView.as_view(),
        name="appcustomers-detail",
    ),
    path(
        "tool-deployments/<str:tool_name>/<str:action>",
        views.ToolDeploymentAPIView.as_view(),
        name="tool-deployments",
    ),
]
