# Standard library
import json

# Third-party
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import App, AppIPAllowList, IPAllowlist


class Command(BaseCommand):
    help = "Update the application's auth0 client information"

    def add_arguments(self, parser):
        parser.add_argument(
            "apps_info",
            type=str,
            help="The path for storing the applications' information",
        )
        parser.add_argument(
            "-t",
            "--token",
            required=True,
            type=str,
            help="input: The token for accessing the github",
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

    def _store_client_id_of_app_env(self, app, env_name, client, group):
        # TODO this part may need to be adjusted if the ticket for
        #  refactoring auth0 client is completed
        if not client:
            return
        existing_data = json.loads(app.description or '{}')
        if not existing_data.get("auth0_clients"):
            existing_data["auth0_clients"] = {}
        if not existing_data["auth0_clients"].get(env_name):
            existing_data["auth0_clients"][env_name] = {}
        existing_data["auth0_clients"][env_name]["client_id"] = client["client_id"]
        existing_data["auth0_clients"][env_name]["group_id"] = group["_id"]
        app.description = json.dumps(existing_data)
        app.save()

    def _create_auth_settings(
            self, env_name, app, github_api_token, app_detail, app_conf, is_first_time):
        """
        Only the application which has been registered in control panel will be
        migrated over into new EKS cluster
        """
        if is_first_time:
            client, group = cluster.App(app, github_api_token).create_auth_settings(
                env_name=env_name,
                disable_authentication=app_detail["disable_authentication"],
                connections=app_detail["connections"],
                app_domain=app_conf['auth0'].get(env_name, {}).get("app_domain")
            )
            self._store_client_id_of_app_env(app, env_name, client, group)
        else:
            cluster.App(app, github_api_token).create_or_update_secret(
                env_name=env_name,
                secret_key=cluster.App.IP_RANGES,
                secret_value=app.env_allowed_ip_ranges(env_name=env_name),
            )

    def _update_data_records(self, env_name, app, app_detail):
        # if app.description field is empty, it means the app hasn't been started yet for migration
        if not app.description:
            backup_json = dict(
                app_name=app.name,
                repo_url=app.repo_url,
                app_url=f"https://{ app.slug }.{settings.APP_DOMAIN}",
                state="in_process"
            )
            app.description = json.dumps(backup_json)
            app.name = app_detail["app_name"]
            app.repo_url = app_detail["repo_url"]
            app.save()

        # update the ip allow list
        if app_detail.get('ip_ranges'):
            ip_allow_list = IPAllowlist.objects.filter(
                name__in=app_detail.get('ip_ranges'))
            AppIPAllowList.objects.update_records(
                app=app,
                env_name=env_name,
                ip_allowlists=ip_allow_list
            )

    def _create_self_defined_secrets(self, env_name, app, github_api_token, app_detail):
        params = app_detail["parameters"]
        if not params:
            return
        cluster.App(app, github_api_token).create_or_update_secrets(
            env_name=env_name,
            secret_data=params
        )

    def _migration_apps(self, apps_info, github_token, app_conf):
        for cnt, app_item in enumerate(apps_info):
            self.stdout.write(f"{cnt}: start to process app {app_item['app_name']}")
            app = App.objects.filter(name=app_item["app_name"]).first()
            if not app:
                self.stdout.write(f"App: {app_item['app_name']} failed to be found in the cpanel DB")
                continue

            is_first_time = not app.description
            app_detail = app_item["migration"]
            for deployment_env in app_detail["envs"]:
                try:
                    self._update_data_records(deployment_env, app, app_detail)
                    self._create_auth_settings(
                        deployment_env, app, github_token, app_detail,
                        app_conf, is_first_time)
                    self._create_self_defined_secrets(deployment_env, app, github_token, app_detail)
                except Exception as ex:
                    self.stdout.write(f"App: {app.name} failed to be processed completed, error: {ex.__str__()}")
            self.stdout.write("Done!")

    def _create_update_ip_allowlist_records(self, ip_allow_list):
        for name, ip_ranges in ip_allow_list.items():
            if not ip_ranges.strip():
                continue

            existing_ip_item = IPAllowlist.objects.filter(name=name).first()
            if existing_ip_item:
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
        self._migration_apps(apps_info, options["token"], app_conf)

