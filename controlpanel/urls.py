from django.conf import settings
from django.urls import include, path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = [
    path("", include("controlpanel.frontend.urls")),
    path("api/cpanel/v1/", include("controlpanel.api.urls")),
    path("api/k8s/", include("controlpanel.kubeapi.urls")),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("events/", include("django_eventstream.urls")),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
        *urlpatterns,
    ]

urlpatterns += staticfiles_urlpatterns()
