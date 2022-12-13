# Third-party
from django.urls import include, path
from rest_framework import routers

# First-party/Local
from controlpanel.api import views

router = routers.DefaultRouter()
router.register("apps", views.AppViewSet)
router.register("apps3buckets", views.AppS3BucketViewSet)
router.register("parameters", views.ParameterViewSet)
router.register("s3buckets", views.S3BucketViewSet)
router.register("tools", views.ToolViewSet, basename="tool")
router.register("userapps", views.UserAppViewSet)
router.register("users", views.UserViewSet)
router.register("users3buckets", views.UserS3BucketViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("repos/", views.tools.RepoApi.as_view(), name="github-repos"),
    path(
        "apps/<int:pk>/customers/",
        views.AppCustomersAPIView.as_view(),
        name="appcustomers-list",
    ),
    path(
        "tool-deployments/<str:tool_name>/<str:action>",
        views.ToolDeploymentAPIView.as_view(),
        name="tool-deployments",
    ),
]
