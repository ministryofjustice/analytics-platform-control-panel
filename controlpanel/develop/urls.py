from django.urls import path

from .views import is_kube_connected_view


urlpatterns = [
    path("kube_connected/", is_kube_connected_view, name="is_kube_connected"),
]
