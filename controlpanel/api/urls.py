from django.urls import include, path
from rest_framework import routers

from controlpanel.api import views


router = routers.DefaultRouter()
router.register("apps", views.AppViewSet)
router.register("apps3buckets", views.AppS3BucketViewSet)
router.register("deployments", views.ToolDeploymentViewSet, basename="deployment")
router.register("groups", views.GroupViewSet)
router.register("s3buckets", views.S3BucketViewSet)
router.register("tools", views.ToolViewSet, basename="tool")
router.register("userapps", views.UserAppViewSet)
router.register("users", views.UserViewSet)
router.register("users3buckets", views.UserS3BucketViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("apps/<int:pk>/customers/", views.AppCustomersAPIView.as_view(), name='appcustomers-list'),
    path(
        "apps/<int:pk>/customers/<str:user_id>/",
        views.AppCustomersDetailAPIView.as_view(),
        name="appcustomers-detail",
    ),
]
