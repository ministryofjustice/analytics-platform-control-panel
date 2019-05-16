from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path


urlpatterns = [
    path("", include("controlpanel.frontend.urls")),
    path("api/cpanel/v1/", include("controlpanel.api.urls")),
    path("api/k8s/", include("controlpanel.kubeapi.urls")),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("events/", include("django_eventstream.urls")),
    # redirect old k8s api requests to new paths
    path("k8s/", include('controlpanel.kubeapi.urls')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
        *urlpatterns,
    ]

urlpatterns += staticfiles_urlpatterns()
