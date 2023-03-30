# Standard library
import json
import csv

# Third-party
from django.core.management.base import BaseCommand, CommandError

# First-party/Local
from controlpanel.api import auth0
from controlpanel.api.models import App


class Command(BaseCommand):
    help = "Update the application's auth0 client information"

    def add_arguments(self, parser):
        parser.add_argument(
            "chosen_apps",
            type=str,
            help="input: The list of apps which require to copy their customers over from old client ",
        )

    def _get_pre_defined_app_list(self, chosen_apps_file):
        """The name of app must be the name on new cluster"""
        list_apps = []
        with open(chosen_apps_file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=",")
            for row in csv_reader:
                list_apps.append(row[0].strip())
        return list_apps

    def _get_group_id_for_prod_env(self, app):
        """Assumption: the client_ids have been stored in the app.description
        if the app has been migrated by running the db_migration_update.py
        """
        try:
            app_migration_info = json.loads(app.description)
        except ValueError:
            app_migration_info = {}
        return app_migration_info.get("auth0_clients", {}).\
            get('prod', {}).get('group_id')

    def _copy_page_customers_from_old_app(
            self, auth0_instance, old_group_id, new_group_id, page=1):
        response = auth0_instance.groups.get_group_members_paginated(
            group_id=old_group_id, page=page)
        user_ids = [item['user_id'] for item in response.get('users') or []]
        is_empty = (len(user_ids) == 0)
        if is_empty:
            return True
        auth0_instance.groups.add_group_members(group_id=new_group_id, user_ids=user_ids)
        return False

    def _copy_customers_from_old_app(self, auth0_instance, old_group_id, new_group_id):
        self.stdout.write("start to process the first page of customers")
        is_finished = self._copy_page_customers_from_old_app(
            auth0_instance, old_group_id, new_group_id)
        counter = 2
        while not is_finished:
            self.stdout.write(f"start to process the page {counter} of customers")
            is_finished = self._copy_page_customers_from_old_app(
                auth0_instance, old_group_id, new_group_id, page=counter)
            counter+=1

    def _migrating_customers(self, list_apps):
        """The assumption
        - Only copy the customers of old app into the client of new live app (prod environment)
        """
        auth0_instance = auth0.ExtendedAuth0()
        for cnt, app_name in enumerate(list_apps):
            self.stdout.write(f"{cnt+1}: start to process app {app_name}")
            found_app = App.objects.filter(name=app_name).first()
            if not found_app:
                self.stdout.write(f"Couldn't find {app_name} from cpanel db")
                continue

            group_id = self._get_group_id_for_prod_env(found_app)
            if not group_id:
                self.stdout.write(f"Couldn't find the group_id from {app_name} description field")
                continue

            old_group_name = found_app.auth0_client_name()
            old_group_id = auth0_instance.groups.get_group_id(found_app.auth0_client_name())
            if not old_group_id:
                self.stdout.write(f"Couldn't find the old group_id based on name {old_group_name}")
                continue

            try:
                self._copy_customers_from_old_app(auth0_instance, old_group_id, group_id)
            except Exception as ex:
                self.stdout.write(f"App: {app_name} failed to be processed completed, error: {ex.__str__()}")
            self.stdout.write("Done!")

    def handle(self, *args, **options):
        try:
            list_apps = self._get_pre_defined_app_list(options["chosen_apps"])
        except ValueError:
            raise CommandError("Failed to load inputs file")
        self._migrating_customers(list_apps)
