from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = "controlpanel.api"

    def ready(self):
        from controlpanel.api import rules
