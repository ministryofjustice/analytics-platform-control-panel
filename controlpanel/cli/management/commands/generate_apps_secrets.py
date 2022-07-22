from django.core.management.base import BaseCommand, CommandError
import json

from controlpanel.api.aws import AWSSecretManager
from django.conf import settings


class Command(BaseCommand):
    help = "Delete an app"

    def add_arguments(self, parser):
        parser.add_argument("app_info", type=str, help="The path for storing the applications' information")

    def _load_json_file(self, file_name):
        with open(file_name) as file:
            data = json.loads(file.read())
        return data

    def _app_aws_secret_name(self, app_name, secret_part):
        return f"{settings.ENV}/apps/{app_name}/{secret_part}"

    def _generate_apps_aws_secrets(self, app_info):
        aws_secret_service = AWSSecretManager()
        for app_item in app_info:
            self.stdout.write("Creating secrets for {}....".format(app_item["app_name"]))
            if app_item.get("auth"):
                aws_secret_service.create_or_update(
                    self._app_aws_secret_name(app_item["app_name"], "auth"),
                    app_item["auth"])
            if app_item.get("parameters"):
                aws_secret_service.create_or_update(
                    self._app_aws_secret_name(app_item["app_name"], "params"),
                    app_item["parameters"])

    def handle(self, *args, **options):
        try:
            app_info = self._load_json_file(options["app_info"])
        except ValueError:
            raise CommandError("Failed to load domain_conf file")
        self._generate_apps_aws_secrets(app_info)
