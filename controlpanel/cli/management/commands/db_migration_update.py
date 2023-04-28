# Standard library
import json

# Third-party
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

# First-party/Local
from controlpanel.api.models import App, AppIPAllowList, IPAllowlist


class Command(BaseCommand):
    help = "Update cpanel database with new application information and the auth settings"

    def add_arguments(self, parser):
        parser.add_argument(
            "apps_info",
            type=str,
            help="The path for storing the applications' information",
        )
        parser.add_argument(
            "-c",
            "--app_conf",
            type=str,
            help="input: The path of the configuration file(JSON)",
        )

    def _load_json_file(self, file_name):
        with open(file_name) as file:
            data = json.loads(file.read())
        return data

    def _update_app_data_records(self, app, app_item):
        migration_json = dict(
            app_name=app.slug,
            repo_url=app_item["repo_url"],
            app_url=f"https://{ app.slug }.{settings.APP_DOMAIN}",
            status="in_progress"
        )
        app_info = dict(
            migration=migration_json,
            auth0_clients=app_item["migration"].get("auth0_clients") or {}
        )
        app.description = json.dumps(app_info)
        app.name = app_item["migration"]["app_name"]
        app.repo_url = app_item["migration"]["repo_url"]
        app.save()

    def _update_app_ip_allow_list(self, app, app_detail):
        # update the ip allow list
        if not app_detail.get('ip_ranges'):
            return
        ip_allow_list = IPAllowlist.objects.filter(
            name__in=app_detail.get('ip_ranges'))
        for env_name in app_detail["envs"]:
            AppIPAllowList.objects.update_records(
                app=app,
                env_name=env_name,
                ip_allowlists=ip_allow_list
            )

    def _update_app_with_migration_info(self, apps_info, app_conf):
        for cnt, app_item in enumerate(apps_info):
            self.stdout.write(f"{cnt+1}: start to process app {app_item['app_name']}")
            app = App.objects.filter(name=app_item["app_name"]).first()
            if not app:
                self.stdout.write(f"App: {app_item['app_name']} failed to be found in the cpanel DB")
                continue

            self._update_app_data_records(app, app_item)
            self._update_app_ip_allow_list(app, app_item["migration"])
            self.stdout.write("Done!")

    def _create_update_ip_allowlist_records(self, ip_allow_list):
        for name, ip_ranges in ip_allow_list.items():
            if not ip_ranges.strip():
                continue

            existing_ip_item = IPAllowlist.objects.filter(name=name).first()
            if existing_ip_item:
                if existing_ip_item.allowed_ip_ranges.strip() != ip_ranges.strip():
                    existing_ip_item.allowed_ip_ranges = ip_ranges
                    existing_ip_item.save()
            else:
                IPAllowlist.objects.create(
                    name=name,
                    allowed_ip_ranges=ip_ranges
                )

    def handle(self, *args, **options):
        try:
            apps_info = self._load_json_file(options["apps_info"])
            app_conf = self._load_json_file(options.get("app_conf"))
        except ValueError:
            raise CommandError("Failed to load inputs file")
        self._create_update_ip_allowlist_records(app_conf["ip_range_lookup_table"])
        self._update_app_with_migration_info(apps_info, app_conf)

