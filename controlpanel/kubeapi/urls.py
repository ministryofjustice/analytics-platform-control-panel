from django.urls import path

from controlpanel.kubeapi import views


urlpatterns = [path("<path:url>", views.KubeAPIProxy.as_view(), name="proxy")]
