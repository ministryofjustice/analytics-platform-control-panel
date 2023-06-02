# Standard library
import json
import csv

# Third-party
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

# First-party/Local
from controlpanel.api import auth0


class Command(BaseCommand):
    help = "Copy the customers of an application from old auth client to new auth clients"

    DEFAULT_ENVS = ["dev", "prod"]

    def add_arguments(self, parser):
        parser.add_argument(
            "chosen_apps",
            type=str,
            help="input: The list of apps which require to copy their customers over from old client ",
        )

    def _get_auth0_client_name(self, app_name, env_name):
        return settings.AUTH0_CLIENT_NAME_PATTERN.format(
                app_name=app_name, env=env_name)

    def _get_pre_defined_app_list(self, chosen_apps_file):
        """The name of app must be the name on new cluster"""
        list_apps = []
        with open(chosen_apps_file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=",")
            next(csv_reader)
            for row in csv_reader:
                old_app_name = row[0].strip().lower().replace('_', '-')
                new_app_name = row[1].strip()
                list_apps.append(dict(
                    old_app_name=old_app_name,
                    app_names=[self._get_auth0_client_name(new_app_name, "prod")]
                ))
        return list_apps

    def _get_full_groups(self, auth0_instance):
        group_list = auth0_instance.groups.get_all()
        groups_info = {}
        for group in group_list:
            groups_info[group.get('name')] = group
        return groups_info

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
        auth0_groups = self._get_full_groups(auth0_instance)
        for cnt, app_info in enumerate(list_apps):
            old_app_name = app_info["old_app_name"]
            self.stdout.write(f"{cnt+1}: start to process app {old_app_name}")

            old_group_id = auth0_groups.get(old_app_name, {}).get("_id")
            if not old_group_id:
                self.stdout.write(f"Couldn't find the old group_id based on name {old_app_name}")
                continue

            for app_name in app_info.get("app_names") or []:
                group_id = auth0_groups.get(app_name, {}).get("_id")
                if not group_id:
                    self.stdout.write(f"Couldn't find the group_id based on name of {app_name}")
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
