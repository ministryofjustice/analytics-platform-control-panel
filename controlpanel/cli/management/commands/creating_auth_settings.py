# Standard library
import json
from time import time

# Third-party
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api import auth0


class DummyApp:

    def __init__(self, app_detail):
        self.app_detail = app_detail
        self.repo_url = app_detail["repo_url"]

    def env_allowed_ip_ranges(self, env_name):
        return self.app_detail["normalised_ip_ranges"]

    @property
    def slug(self):
        return self.app_detail["app_name"]

    def auth0_client_name(self, env_name=None):
        allowed_length = settings.AUTH0_CLIENT_NAME_LIMIT - len(env_name or "")
        client_name = self.slug[0:allowed_length-1]
        return settings.AUTH0_CLIENT_NAME_PATTERN.format(
            app_name=client_name, env=env_name)

    def app_url_name(self, env_name):
        format_pattern = settings.APP_URL_NAME_PATTERN.get(env_name.upper())
        if not format_pattern:
            format_pattern = settings.APP_URL_NAME_PATTERN.get("DEFAULT")
        if format_pattern:
            return format_pattern.format(app_name=self.slug, env=env_name)
        else:
            return self.slug

    def save_auth_settings(self, env_name, client=None, group=None):
        pass


class Command(BaseCommand):
    help = "Create the application's auth0 clients per environment and generate github secrets"

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

    def _store_client_id_of_app_env(self, env_name, client, group, app_detail):
        if not client:
            return
        existing_data = app_detail
        if not existing_data.get("auth0_clients"):
            existing_data["auth0_clients"] = {}
        if not existing_data["auth0_clients"].get(env_name):
            existing_data["auth0_clients"][env_name] = {}
        existing_data["auth0_clients"][env_name]["client_id"] = client["client_id"]
        if group:
            existing_data["auth0_clients"][env_name]["group_id"] = group["_id"]

    def _get_auth0_client_name(self, app_name, env_name):
        return settings.AUTH0_CLIENT_NAME_PATTERN.format(
                app_name=app_name, env=env_name)

    def _create_initial_users(self, cluster_instance, group, initial_user_ids):
        if not group:
            return
        if not initial_user_ids:
            return
        cluster_instance.auth0_instance.groups.add_group_members(
            group_id=group["_id"], user_ids=initial_user_ids)

    def _is_client_created(self, env_name, app_detail):
        return app_detail.get("auth0_clients", {}).get(env_name, {}).get("client_id")

    def _inject_auth_settings_to_github(self, env_name, cluster_instance, app_detail):
        # calling the internal function of a class is only for app migration
        # will be removed after app migration is done.
        client = None
        if not app_detail["disable_authentication"]:
            client_id = app_detail["auth0_clients"][env_name]["client_id"]
            client = cluster_instance.auth0_instance.clients.get(client_id)
        cluster_instance._create_secrets(env_name, client=client)
        cluster_instance._create_env_vars(
            env_name,
            app_detail["disable_authentication"],
            app_detail["connections"] or [],
            client=client,
        )

    def _create_auth_settings(
            self, env_name, cluster_instance, app_detail, app_conf, initial_user_ids):
        """
        Only the application which has been registered in control panel will be
        migrated over into new EKS cluster
        """
        if self._is_client_created(env_name, app_detail):
            self._inject_auth_settings_to_github(env_name, cluster_instance, app_detail)
        else:
            client, group = cluster_instance.create_auth_settings(
                env_name=env_name,
                disable_authentication=app_detail["disable_authentication"],
                connections=app_detail["connections"],
                app_domain=app_conf['auth0'].get(env_name, {}).get("app_domain")
            )
            self._store_client_id_of_app_env(env_name, client, group, app_detail)
            self._create_initial_users(cluster_instance, group, initial_user_ids)

    def _create_self_defined_secrets(self, env_name, cluster_instance, app_detail):
        params = app_detail.get("parameters")
        if not params:
            return
        cluster_instance.create_or_update_secrets(
            env_name=env_name,
            secret_data=params
        )

    def _get_intial_user_ids(self, cluster_instance, app_conf):
        if not app_conf.get("initial_users"):
            return []
        user_ids = cluster_instance.auth0_instance.users.add_users_by_emails(
            app_conf.get("initial_users"), user_options={"connection": "email"})
        return user_ids

    def _is_target_repo_ready(self,  cluster_instance):
        try:
            cluster_instance.get_deployment_envs()
        except Exception as ex:
            self.stdout.write(f"App: {cluster_instance.app['app_name']} has problem with repo,"
                              f" error: {ex.__str__()}")
            return False
        return True

    def _migration_apps(self, apps_info, github_token, app_conf):
        auth0_instance = auth0.ExtendedAuth0()
        cluster_instance = cluster.App(None, github_token, auth0_instance)
        initial_user_ids = self._get_intial_user_ids(cluster_instance, app_conf)
        for cnt, app_item in enumerate(apps_info):
            self.stdout.write(f"{cnt+1}: start to process app {app_item['app_name']}")

            app_detail = app_item["migration"]
            dummpy_app = DummyApp(app_detail)
            cluster_instance.app = dummpy_app

            # Check whether the target_repo meet the criteria
            if not self._is_target_repo_ready(cluster_instance):
                continue

            for deployment_env in app_detail["envs"]:
                try:
                    self._create_auth_settings(
                        deployment_env, cluster_instance, app_detail,
                        app_conf, initial_user_ids)
                    self._create_self_defined_secrets(
                        deployment_env, cluster_instance, app_detail)
                except Exception as ex:
                    self.stdout.write(f"App: {app_item['app_name']} failed to be processed completed, error: {ex.__str__()}")
            self.stdout.write("Done!")

    def _save_to_file(self, apps_info, output_file_name):
        with open(output_file_name, "w") as f:
            json.dump(apps_info, f, indent=4)

    def _default_output_file(self):
        return "./new_apps_info{}.json".format(int(time()))

    def handle(self, *args, **options):
        try:
            apps_info = self._load_json_file(options["apps_info"])
            app_conf = self._load_json_file(options.get("app_conf"))
        except ValueError:
            raise CommandError("Failed to load inputs file")
        self._migration_apps(apps_info, options["token"], app_conf)
        self._save_to_file(apps_info, self._default_output_file())

