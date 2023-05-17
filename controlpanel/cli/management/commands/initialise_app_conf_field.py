# Standard library
import json

# Third-party
from django.core.management.base import BaseCommand, CommandError

# First-party/Local
from controlpanel.api import auth0
from controlpanel.api.models import App


class Command(BaseCommand):
    help = "Initialise app.app_conf field for existing dashboard apps"

    def add_arguments(self, parser):
        pass

    def _get_full_groups(self, auth0_instance):
        group_list = auth0_instance.groups.get_all()
        groups_info = {}
        for group in group_list:
            groups_info[group.get('name')] = group
        return groups_info

    def _get_full_clients(self, auth0_instance):
        client_list = auth0_instance.clients.get_all()
        clients_info = {}
        for client in client_list:
            clients_info[client.get('name')] = client
        return clients_info

    def _get_auth0_name(self, app):
        app_name = None
        if app.migration_info:
            app_name = app.migration_info.get("app_name")
        if not app_name:
            app_name = app.slug
        return app_name

    def _get_auth0_client_info(self, app):
        try:
            return json.loads(app.description).get("auth0_clients", {})
        except ValueError:
            return {}

    def _initialise_auth_info_to_new_field(self):
        auth0_instance = auth0.ExtendedAuth0()
        groups_info = self._get_full_groups(auth0_instance)
        clients_info = self._get_full_clients(auth0_instance)
        apps_list = App.objects.all()
        for cnt, app in enumerate(apps_list):
            self.stdout.write(f"{cnt+1}: start to process app {app.slug}")
            client = clients_info.get(self._get_auth0_name(app))
            auth_settings = dict()
            if client:
                auth_settings.update(dict(client_id=client["client_id"]))
            group = groups_info.get(app.slug)
            if group:
                auth_settings.update(dict(group_id=group["_id"]))

            new_auth0_clients = self._get_auth0_client_info(app)
            if not auth_settings and not new_auth0_clients:
                self.stdout.write(f"{cnt + 1}: No clients is found for app {app.slug}!")
                continue
            else:
                if not app.app_conf:
                    app.app_conf = dict()
                if App.KEY_WORD_FOR_AUTH_SETTINGS not in app.app_conf:
                    app.app_conf[App.KEY_WORD_FOR_AUTH_SETTINGS] = {}

            if auth_settings:
                app.app_conf[App.KEY_WORD_FOR_AUTH_SETTINGS][App.DEFAULT_AUTH_CATEGORY] = auth_settings

            for env_name, env_info in new_auth0_clients.items():
                app.app_conf[App.KEY_WORD_FOR_AUTH_SETTINGS][env_name] = env_info

            app.save()
            self.stdout.write(f"{cnt+1}: app {app.slug} done!")

    def handle(self, *args, **options):
        self._initialise_auth_info_to_new_field()
