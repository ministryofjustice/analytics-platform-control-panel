# Third-party
from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "controlpanel.api"

    def ready(self):
        # First-party/Local
        from controlpanel.api import rules  # noqa: F401
