# Third-party
from django.urls import path

# First-party/Local
from controlpanel.kubeapi import views

urlpatterns = [path("<path:url>", views.KubeAPIProxy.as_view(), name="proxy")]
