from django.conf import settings
from django.contrib import admin
from controlpanel.api.views import health_check
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django_prometheus import exports

def worker_test(request):
    from django.http import HttpResponse
    from controlpanel.celery import debug_task

    result = debug_task.delay()
    print(result.get())

    return HttpResponse("working")

urlpatterns = [
    path("test/", worker_test),
    path("", include("controlpanel.frontend.urls")),
    path("admin/", admin.site.urls),
    path("api/cpanel/v1/", include("controlpanel.api.urls")),
    path("api/k8s/", include("controlpanel.kubeapi.urls")),
    path("oidc/", include("mozilla_django_oidc.urls")),
    # redirect old k8s api requests to new paths
    path("k8s/", include('controlpanel.kubeapi.urls')),
    path("health/", health_check),
    path("metrics", exports.ExportToDjangoView, name="prometheus-django-metrics"),
]

if "controlpanel.develop" in settings.INSTALLED_APPS:
    urlpatterns += [
        path("develop/", include('controlpanel.develop.urls')),
    ]

urlpatterns += staticfiles_urlpatterns()
