import json
from copy import deepcopy
import os
import csv
from urllib.parse import urlparse
from django.core.management.base import BaseCommand, CommandError

from controlpanel.api.github import GithubAPI
from controlpanel.api.auth0 import ExtendedAuth0
from controlpanel.api.aws import AWSParameterStore
from controlpanel.api.models import Parameter, App
from django.conf import settings


class Command(BaseCommand):

    """"
    This command line tool is to retrieve full information about an app hosted on AP, the steps will be
    - Read the list of applications from control panel's DB
    - Collect deployment info by reading the deploy.json from the app's github repo
    - Collect the application info from auth0 including the connections information
    - Read parameters from AWS parameters
    Record those information in the json file, and also prepare 2 new parts for app migration:=
    - Auth part: includes the key information from auth0 and deploy.json which will be the content of auth AWS secret
    - Parameter part: includes the app's parameters stored in AWS param store which
        will be the content of params AWS secret
    The outcome will be stored as json file, app_info_example.json is the example

    Setting: in order to be able to run the script and read the information from correct AWS account,the environment
    needs to be setup properly
        - DB connection
        - AWS landing account or credential for AWS data account
        - Credential to be able to call Auth0 API
    """
    help = "Retrieve all those information related to an app including github, auth0 and AWS parameters " \
           "from AWS data account"

    def add_arguments(self, parser):
        parser.add_argument("-t", "--token", required=True, type=str,
                            help="The token for accessing the github")
        parser.add_argument("-f", "--file", required=True, type=str,
                            help="The path for storing the applications' information")
        # The example of app_conf, app_conf_example.json, is provided.
        parser.add_argument("-c", "--app_conf", type=str,
                            help="The configuration file for app migration")
        parser.add_argument("-oa", "--oaudit", type=str,
                            help="The path of storing application's information as csv")

    def _add_new_app(self, apps_info, app_name):
        if app_name not in apps_info:
            apps_info[app_name] = {
                "app_name": app_name,
                "registered_in_cpanel": False,
                "can_be_migrated": False,
                "has_repo": False,
                "auth0_client": {},
                "parameters": {},
                "auth": {},
            }

    def _init_app_info(self, app_info):
        applications = App.objects.all()
        for app in applications:
            self._add_new_app(app_info, app.name)
            app_info[app.name]["registered_in_cpanel"] = True

    def _normalize_ip_ranges(self, app_item, app_conf):
        if app_item.get("allowed_ip_ranges") and app_conf.get('ip_range_lookup_table'):
            lookup = app_conf['ip_range_lookup_table']
            if 'Any' in app_item.get("allowed_ip_ranges"):
                ip_ranges = ['']
            else:
                ip_ranges = [lookup[item] for item in app_item["allowed_ip_ranges"] if item in lookup]
            not_found = [item for item in app_item.get("allowed_ip_ranges") if item not in lookup]
            if not_found:
                self.stdout.write("Warning: Couldn't find ip_range for {}".format(",".join([not_found])))
            if not ip_ranges:
                ip_ranges = [lookup['DOM1']]

            app_item["normalised_allowed_ip_ranges"] = ",".join(ip_ranges)

    def _collect_apps_deploy_info(self, github_token, apps_info, audit_data_keys, app_conf):
        """
        To gain access to the github repo proves difficult than I thought, for now I will use the
        id_token from my login account, unless there is a need for frequent usage, then we need to
        implement device code flow

        The process of reading all those repo and exacting the fields from deploy.json is quite time consuming
        """
        github_api = GithubAPI(github_token)
        all_repos = github_api.get_all_repositories()
        for repo in all_repos:
            self.stdout.write("Reading repo {}....".format( repo.full_name))
            try:
                deployment_json = github_api.read_app_deploy_info(repo_instance=repo)
                if not deployment_json:
                    continue
                if repo.name in apps_info:
                    self.stdout.write("**Found deploy.json under this repo**")
                else:
                    self.stdout.write("**Found deploy.json under this repo, "
                                      "but the app is not registered in Control panel **")

                self._add_new_app(apps_info, repo.name)
                apps_info[repo.name]["has_repo"] = True
                apps_info[repo.name]["deployment"] = deployment_json
                apps_info[repo.name]["auth"] = deepcopy(deployment_json)
                self._normalize_ip_ranges(apps_info[repo.name]["auth"], app_conf)
                audit_data_keys.extend([key for key in deployment_json.keys() if key not in audit_data_keys])
            except Exception as ex:
                self.stdout.write(f"Failed to load deploy.json due to the error: {str(ex)}")

    def _process_urls(self, callback_urls, domains_mapping):
        """ A new set of callbacks will be added based on the domains_mappings, the old ones will be still kept """
        new_callback_urls = []
        new_callback_urls.extend(callback_urls)
        for callback in callback_urls:
            app_domain = urlparse(callback).netloc
            for domain, new_app_domain in domains_mapping.items():
                if domain in app_domain:
                    new_callback_urls.append(callback.replace(domain, new_app_domain))
                else:
                    new_callback_urls.append(callback)
        return list(set(new_callback_urls))

    def _process_application_name(self, app_name, name_pattern):
        """ only a few pre-defined variables will be supported
         - ENV: settings.ENV
         - app_name: application_name.
        """
        new_app_name = name_pattern.replace("{ENV}", settings.ENV)
        new_app_name = new_app_name.replace("{app_name}", app_name)
        return new_app_name

    def _remove_sensitive_fields(self, client):
        # Remove some fields and keep the original client info under "auth0_client"
        del client["signing_keys"]
        del client["client_secret"]

    def _collect_app_auth0_basic_info(self, auth0_instance, apps_info, app_conf):
        """
        The function to collect the auth0 information for an app
        """
        clients = auth0_instance.clients.get_all()
        clients_id_name_map = {}
        for client in clients:
            if client['name'] not in apps_info:
                self.stdout.write("{} is not recognised as an app managed on our AP platform.".format(client['name']))
                continue

            self.stdout.write("Reading app({})'s auth0 information....".format(client['name']))
            self._remove_sensitive_fields(client)

            apps_info[client['name']]["auth0_client"] = client

            # Construct the information required for aws secret
            apps_info[client['name']]["new_app_name"] = \
                self._process_application_name(client['name'], app_conf.get('app_name_pattern'))
            apps_info[client['name']]["auth"]["client_id"] = client["client_id"]
            apps_info[client['name']]["auth"]["callbacks"] = self._process_urls(
                client.get("callbacks", []), app_conf.get("domains_mapping") or {})
            apps_info[client['name']]["auth"]["allowed_origins"] = self._process_urls(
                client.get("allowed_origins", []), app_conf.get("domains_mapping") or {})
            clients_id_name_map[client["client_id"]] = client['name']
        return clients_id_name_map

    def _collection_apps_auth0_connections(self, auth0_instance, apps_info, clients_id_name_map):
        connections = auth0_instance.connections.get_all()
        for connection in connections:
            for enabled_client_id in connection["enabled_clients"] or []:
                client_name = clients_id_name_map.get(enabled_client_id)
                if not client_name:
                    continue

                if not apps_info[client_name].get("connections"):
                    apps_info[client_name]["auth0_client"]["connections"] = []
                apps_info[client_name]["auth0_client"]["connections"].append(connection["name"])
                if not connection.get('enabled_app_names'):
                    connection['enabled_app_names'] = []
                connection['enabled_app_names'].append(client_name)
        return connections

    def _collection_app_refresh_tokens(self, auth0_instance, app_auth0_info):
        """
        Retrieving refresh token needs to use device_credential api. This api has
        mandatory parameter: user_id and strangely ignore the client_id and include_total fields which
        cause the trouble for using this api, we need to go through each user by user which is huge base to
        find fount which client does generate refresh_token, rather than through clients, also because it
        doesn't return total info, we couldn't know the exact number of the token at the moment,
        so will raise the issue to auth0 and wait.
        """
        pass

    def _collection_app_parameters_store_info(self, apps_info):
        """
        Read all the existing parameters for an app from aws parameter store
        control panel database has the apps' parameters in the database.
        """
        parameters = Parameter.objects.all()
        aws_param_service = AWSParameterStore()
        for parameter in parameters:
            # derive the application name from the role_name
            app_name = parameter.role_name.replace("{}_app_".format(settings.ENV), "")

            self.stdout.write("Reading parameter, {}, for the app - {}".format(parameter.name, app_name))

            self._add_new_app(apps_info, app_name)
            para_response = aws_param_service.get_parameter(parameter.name)
            apps_info[app_name]["parameters"][parameter.key] = para_response["Parameter"]["Value"]

    def _gather_apps_full_info(self, github_token, app_conf, apps_info, audit_data_keys):
        auth0_instance = ExtendedAuth0()

        self.stdout.write("1. Collecting the deployment information of each app from github")
        self._collect_apps_deploy_info(github_token, apps_info, audit_data_keys, app_conf)

        self.stdout.write("2. Collecting the auth0 client information of each app.")
        clients_id_name_map = self._collect_app_auth0_basic_info(auth0_instance, apps_info, app_conf)

        self.stdout.write("3. Collecting the connections information of each app from auth0")
        self._collection_apps_auth0_connections(auth0_instance, apps_info, clients_id_name_map)

        self.stdout.write("4. Collecting the parameters of each from AWS parameter store")
        self._collection_app_parameters_store_info(apps_info)

    def _load_json_file(self, file_name):
        if not file_name:
            return {}

        if not os.path.exists(file_name):
            raise CommandError("The file({}) doesn't exist!".format(file_name))
        try:
            with open(file_name) as file:
                data = json.loads(file.read())
            return data
        except ValueError:
            raise CommandError("Failed to load domain_conf file")

    def _save_to_file(self, apps_info, output_file_name):
        with open(output_file_name, 'w') as f:
            json.dump(apps_info, f, indent=4)

    def _convert_list_to_str(self, value):
        if type(value) is list:
            return ",".join(value)
        if type(value) is bool:
            return "Y" if value else "N"
        else:
            return str(value)

    def _save_app_info_as_csv(self, csv_file, apps_info, audit_data_keys):
        with open(csv_file, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(audit_data_keys)
            for app_name, app_item in apps_info.items():
                data_row = []
                for data_key in audit_data_keys:
                    if data_key in app_item:
                        data_row.append(self._convert_list_to_str(app_item[data_key]))
                    elif data_key in (app_item.get("auth0_client") or []):
                        data_row.append(self._convert_list_to_str(app_item["auth0_client"][data_key]))
                    elif data_key in (app_item.get("deployment") or []):
                        data_row.append(self._convert_list_to_str(app_item["deployment"][data_key]))
                    elif data_key == 'has_auth0':
                        data_row.append("Y" if app_item.get("auth0_client") else "N")
                    elif data_key == 'has_deployment':
                        data_row.append("Y" if app_item.get("deployment") else "N")
                    elif data_key == 'has_parameters':
                        data_row.append("Y" if app_item.get("parameters") else "N")
                    elif data_key == 'auth_connections':
                        auth_conn_str = self._convert_list_to_str((app_item.get('auth0_client') or {}).
                                                                  get("connections", []))
                        data_row.append(auth_conn_str)
                    else:
                        data_row.append("")
                        continue

                writer.writerow(data_row)

    def _check_migration_date_of_app(self, apps_info):
        for app_name, app_item in apps_info.items():
            if app_item.get('registered_in_cpanel') and app_item.get('deployment') and app_item.get('auth0_client'):
                app_item["can_be_migrated"] = True

    def handle(self, *args, **options):
        app_conf = self._load_json_file(options.get("app_conf"))
        apps_info = {}
        audit_data_keys = ["app_name", "registered_in_cpanel", "can_be_migrated", "has_auth0", "has_parameters",
                           "has_repo", "has_deployment", "client_id", "callbacks", "grant_types", "auth_connections"]
        self._init_app_info(apps_info)
        self._gather_apps_full_info(options["token"], app_conf, apps_info, audit_data_keys)
        self._save_to_file(list(apps_info.values()), options["file"])

        self._check_migration_date_of_app(apps_info)

        if options.get('oaudit'):
            self._save_app_info_as_csv(options.get('oaudit'), apps_info, audit_data_keys)
