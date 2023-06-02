# Standard library
import csv
from datetime import datetime

# Third-party
from auth0.v3.exceptions import Auth0Error
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

# First-party/Local
from controlpanel.api import auth0


class Command(BaseCommand):
    help = "Clear up the auth0 resources for app migration"

    CSV_OUTPUT_FILE_NAME = "./users_list.csv"
    SCRIPT_LOG_FILE_NAME = "./clear_up_auth0_resources_log.txt"
    CSV_COLUMNS = ["user_id", "email", "username", "created_at", "updated_at", "last_login", "logins_count"]

    CSV_OUTPUT_FOR_GROUP_MEMBER_FILE_NAME = "./removed_group_members.csv"

    MAX_MONTHS_TO_KEEP = 11
    MAX_MONTHS_FOR_NEVER_LOGIN = 11

    SKIP_GROUP_NAMES = []

    def add_arguments(self, parser):
        pass

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
                old_app_name = row[0].strip()
                new_app_name = row[1].strip()
                list_apps.append(dict(
                    old_app_name=old_app_name,
                    app_names=[self._get_auth0_client_name(new_app_name, "prod")]
                ))
        return list_apps

    def _get_full_groups(self, auth0_instance):
        group_list = auth0_instance.groups.get_all()
        groups_info = {}
        collect_removable_groups = []
        for group in group_list:
            if "roles" not in group:
                self._log_info(f"{group['name']} doesn't have role linked with")
                collect_removable_groups.append(group)
            else:
                if len(group["roles"]) > 1:
                    self._log_info(f"{group['name']} have more than more roles linked")
                    collect_removable_groups.append(group)
                else:
                    groups_info[group["roles"][0]] = group
        return groups_info, collect_removable_groups

    def _get_full_clients(self, auth0_instance):
        client_list = auth0_instance.clients.get_all()
        client_info = {}
        for client in client_list:
            client_info[client.get('client_id')] = client
        return client_info

    def _get_full_roles(self, auth0_instance):
        roles_list = auth0_instance.roles.get_all()
        return roles_list

    def load_auth0_resources(self, auth0_instance):
        auth0_roles = self._get_full_roles(auth0_instance)
        auth0_clients = self._get_full_clients(auth0_instance)
        auth0_groups, collect_removable_groups = self._get_full_groups(auth0_instance)
        return auth0_roles, auth0_clients, auth0_groups, collect_removable_groups

    def collect_unused_roles(self, auth0_roles, auth0_clients):
        collect_removable_roles = []
        for cnt, role in enumerate(auth0_roles):
            self._log_info(f"{cnt+1}: start to process {role['applicationId']} - role {role['name']}")
            if not auth0_clients.get(role['applicationId']):
                self._log_info(f"{role['applicationId']} is redundant!")
                collect_removable_roles.append(role)
            else:
                self._log_info(f"{auth0_clients[role['applicationId']]['name']} has been found!")
            self._log_info("Done!")
        return collect_removable_roles

    def clear_up_unused_groups(self, auth0_instance, collect_removable_groups):
        for cnt, group in enumerate(collect_removable_groups):
            self._log_info(f"{cnt}----delete the group ({group['name']})")
            if group.get("members"):
                auth0_instance.groups.delete_group_members(group.get("members"), group["_id"])
            auth0_instance.groups.delete(group["_id"])

    def clear_up_unused_permission_related_resources(
            self, auth0_instance, collect_removable_roles, auth0_groups):
        for cnt, role in enumerate(collect_removable_roles):
            group = auth0_groups.get(role["_id"])
            if not group:
                self._log_info(f"{role['applicationId']} cannot find the group")
            else:
                self._log_info(f"{cnt}----{role['applicationId']} find the group ({group['name']})")
                if group.get("members"):
                    auth0_instance.groups.delete_group_members(group.get("members"), group["_id"])
                auth0_instance.groups.delete(group["_id"])
            auth0_instance.roles.delete(role["_id"])
            for permission_id in role["permissions"]:
                auth0_instance.permissions.delete(permission_id)

    def clear_up_some_apps_members(self, auth0_instance, group_ids):
        for group_id in group_ids:
            members = auth0_instance.groups.get_group_members(group_id)
            if not members:
                continue
            for cnt, member in enumerate(members):
                self._log_info(f"{cnt}----Deleting {member['user_id']}")
                auth0_instance.groups.delete_group_members([member["user_id"]], group_id)

    def _read_users_by_page(self, auth0_instance, page=0):
        query_string = 'identities.connection:"email"'
        search_engine = "v3"
        sort = "last_login:1"
        response = auth0_instance.users.list(q=query_string, search_engine=search_engine, page=page, sort=sort)
        users = response.get("users") or []
        return users, len(users) == 0

    def _write_row_into_csv(self, auth0_instance, writer, users):
        for user in users:
            row = []
            for column in self.CSV_COLUMNS:
                row.append(user.get(column))
            groups = auth0_instance.users.get_user_groups(user["user_id"])
            group_names = [item["name"] for item in groups]
            row.append("|".join(group_names))
            writer.writerow(row)

    def read_ancient_users(self, auth0_instance):
        with open(self.CSV_OUTPUT_FILE_NAME, "w") as f:
            writer = csv.writer(f)
            writer.writerow(self.CSV_COLUMNS + ["groups"])

            page = 0
            self._log_info(f"start to process the page {page} of users")
            users, is_finished = self._read_users_by_page(auth0_instance)
            self._write_row_into_csv(auth0_instance, writer, users)
            while not is_finished:
                page += 1
                self._log_info(f"start to process the page {page} of users")
                users, is_finished = self._read_users_by_page(auth0_instance, page=page)
                self._write_row_into_csv(auth0_instance, writer, users)

    def _is_ancient_user(self, user_info):
        if not user_info.get("last_login"):
            created_at = user_info["created_at"]
            pos = created_at.find(".")
            created_at = datetime.strptime(created_at[0:pos], '%Y-%m-%dT%H:%M:%S')
            return (datetime.now() - created_at).days > 30 * self.MAX_MONTHS_FOR_NEVER_LOGIN
        else:
            last_login = user_info["last_login"]
            pos = last_login.find(".")
            last_login = datetime.strptime(last_login[0:pos], '%Y-%m-%dT%H:%M:%S')
            return (datetime.now() - last_login).days > 30 * self.MAX_MONTHS_TO_KEEP

    def _log_info(self, info):
        self.stdout.write(info)
        with open(self.SCRIPT_LOG_FILE_NAME, "a") as f:
            f.write(info)
            f.write("\n")

    def _log_remove_group_member(self, group, user_info):
        with open(self.CSV_OUTPUT_FOR_GROUP_MEMBER_FILE_NAME, "a") as f:
            data = [
                group["name"],
                group["_id"],
                user_info["email"],
                user_info["created_at"],
                user_info["updated_at"],
                user_info.get("last_login") or '',
                str(user_info.get("logins_count") or 0),
            ]
            f.write(",".join(data))
            f.write("\n")

    def clear_up_ancient_users_from_groups(self, auth0_instance, auth0_groups):
        for group in auth0_groups.values():
            if group["name"] in self.SKIP_GROUP_NAMES:
                continue

            self._log_info(f'group ({group["name"]}) has {len(group.get("members") or [])} number of users.')
            ancient_users = []
            non_exist_users = []
            for member_id in group.get("members") or []:
                try:
                    user_info = auth0_instance.users.get(member_id)
                    if self._is_ancient_user(user_info):
                        ancient_users.append(member_id)
                        self._log_remove_group_member(group, user_info)
                        self._log_info(f'Removing the member {user_info["email"]}')
                        auth0_instance.groups.delete_group_members([member_id], group["_id"])
                except Auth0Error as error:
                    if error.status_code == 404:
                        non_exist_users.append(member_id)
                        self._log_info(f'Removing the member {member_id}')
                        auth0_instance.groups.delete_group_members([member_id], group["_id"])

            self._log_info(f'group ({group["name"]}) has {len(ancient_users)} number of ancient users, '
                           f'{len(non_exist_users)} number of non-existed users')

    def handle(self, *args, **options):
        auth0_instance = auth0.ExtendedAuth0()
        auth0_roles, auth0_clients, auth0_groups, collect_removable_groups = \
            self.load_auth0_resources(auth0_instance)
        collect_removable_roles = self.collect_unused_roles(auth0_roles, auth0_clients)
        self.clear_up_unused_permission_related_resources(
            auth0_instance, collect_removable_roles, auth0_groups)
        self.clear_up_unused_groups(auth0_instance, collect_removable_groups)
        self.clear_up_ancient_users_from_groups(auth0_instance, auth0_groups)

