# Standard library
import json

# Third-party
from django.core.management.base import BaseCommand, CommandError

# First-party/Local
from controlpanel.api.auth0 import ExtendedAuth0


class Command(BaseCommand):
    help = "Update the application's auth0 client information"

    def add_arguments(self, parser):
        parser.add_argument(
            "app_info",
            type=str,
            help="The path for storing the applications' information",
        )

    def _load_json_file(self, file_name):
        with open(file_name) as file:
            data = json.loads(file.read())
        return data

    def _update_app_auth0_client_info(self, app_info):
        """
        Only the application which has been registered in control panel will be
        migrated over into new EKS cluster
        """
        auth0_instance = ExtendedAuth0()
        for app_item in app_info:
            if not app_item["can_be_migrated"]:
                continue
            client_id = app_item["auth"]["client_id"]
            auth0_instance.clients.update(
                client_id,
                body={
                    "callbacks": app_item["auth"]["callbacks"],
                    "allowed_origins": app_item["auth"]["allowed_origins"],
                    "allowed_logout_urls": app_item["auth"]["allowed_logout_urls"],
                    "name": app_item["new_app_name"],
                },
            )

    def handle(self, *args, **options):
        try:
            app_info = self._load_json_file(options["app_info"])
        except ValueError:
            raise CommandError("Failed to load domain_conf file")
        self._update_app_auth0_client_info(app_info)
