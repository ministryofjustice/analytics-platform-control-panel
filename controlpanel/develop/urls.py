from django.urls import path

from .views import develop_index


urlpatterns = [
    path("", develop_index, name="develop_index"),
]
