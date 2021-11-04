from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django_prometheus import exports

urlpatterns = [
    path("", include("controlpanel.frontend.urls")),
    path("api/cpanel/v1/", include("controlpanel.api.urls")),
    path("api/k8s/", include("controlpanel.kubeapi.urls")),
    path("oidc/", include("mozilla_django_oidc.urls")),
    # redirect old k8s api requests to new paths
    path("k8s/", include('controlpanel.kubeapi.urls')),
    path("health/", include('health_check.urls')),
    path("metrics", exports.ExportToDjangoView, name="prometheus-django-metrics"),
]

urlpatterns += staticfiles_urlpatterns()
