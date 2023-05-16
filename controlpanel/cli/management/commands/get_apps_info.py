# Standard library
import csv
import json
import os
from copy import deepcopy
from time import time
from urllib.parse import urlparse, urlunparse

# Third-party
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# First-party/Local
from controlpanel.api.auth0 import ExtendedAuth0
from controlpanel.api.aws import AWSParameterStore
from controlpanel.api.github import GithubAPI, extract_repo_info_from_url
from controlpanel.api.models import App, Parameter


class Command(BaseCommand):

    """ "
    This command line tool is to retrieve full information about an app
    hosted on AP, the steps will be
    - Read the list of applications from control panel's DB
    - Collect deployment info by reading the deploy.json from the app's github repo
    - Collect the application info from auth0 including the connections information
    - Read parameters from AWS parameters
    Record those information in the json file, and also prepare 2 new parts
    for app migration:=
    - Auth part: includes the key information from auth0 and deploy.json which
    will be the content of auth AWS secret
    - Parameter part: includes the app's parameters stored in AWS param store which
        will be the content of params AWS secret
    The outcome will be stored as json file, app_info_example.json is the example

    Setting: in order to be able to run the script and read the information
    from correct AWS account,the environment
    needs to be setup properly
        - DB connection
        - AWS landing account or credential for AWS data account
        - Credential to be able to call Auth0 API
    """

    help = (
        "Retrieve all those information related to an app including github, auth0 and AWS parameters "  # noqa: E501
        "from AWS data account"
    )

    AUDIT_DATA_KEYS = [
        "app_name",
        "registered_in_cpanel",
        "deployed_on_alpha",
        "can_be_migrated",
        "has_auth0",
        "has_parameters",
        "has_repo",
        "has_deployment",
        "client_id",
        "callbacks",
        "grant_types",
        "auth_connections",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            "--token",
            required=True,
            type=str,
            help="input: The token for accessing the github",
        )
        # The example of app_conf, app_conf_example.json, is provided.
        parser.add_argument(
            "-c",
            "--app_conf",
            type=str,
            help="input: The path of the configuration file(JSON)",
        )
        parser.add_argument(
            "-a",
            "--chosen_apps",
            type=str,
            help="input: The list of apps for migration",
        )
        parser.add_argument(
            "-p",
            "--pods",
            type=str,
            help="input: The path of the file(CSV) providing the list of apps' pods "  # noqa: E501
            "deployed on alpha cluster",
        )
        parser.add_argument(
            "-f",
            "--file",
            required=True,
            type=str,
            help="output: Specify the path for the file(JSON) storing outcome from the script",  # noqa: E501
        )
        parser.add_argument(
            "-l",
            "--log",
            type=str,
            help="output: Specify the path for the error log file(TXT) generated from the script",  # noqa: E501
        )
        parser.add_argument(
            "-oa",
            "--oaudit",
            type=str,
            help="output: Specify the path of the file(CSV) containing the summary of applications info"  # noqa: E501
            "generated from the script",
        )

    def _add_new_app(self, apps_info, app_name):
        if app_name not in apps_info:
            apps_info[app_name] = {
                "app_name": app_name,
                "registered_in_cpanel": False,
                "can_be_migrated": False,
                "has_repo": False,
                "auth0_client": {},
                "parameters": {},
                "migration": {"envs":{}, "connections":[]},
            }

    def _init_app_info(self, app_scope):
        app_info = {}
        for app_name, app_detail in app_scope.items():
            self._add_new_app(app_info, app_name)
            app_info[app_name]["repo_url"] = app_detail["source_repo_url"]
            app_info[app_name]["migration"]["app_name"] = app_detail["new_app_name"]
            app_info[app_name]["migration"]["repo_url"] = app_detail["repo_url"]
            app_info[app_name]["migration"]["envs"] = app_detail["envs"]
        return app_info

    def _log_error(self, info):
        with open(self._error_log_file_name, "a") as f:
            f.write(info)
            f.write("\n")

    def _normalize_ip_ranges(self, app_name, app_item, app_conf):
        if app_item.get("ip_ranges") and app_conf.get("ip_range_lookup_table"):
            lookup = app_conf["ip_range_lookup_table"]
            if "Any" in app_item.get("ip_ranges"):
                ip_ranges = [""]
            else:
                ip_ranges = [
                    lookup[item]
                    for item in app_item["ip_ranges"]
                    if item in lookup
                ]
            not_found = [
                item for item in app_item.get("ip_ranges") if item not in lookup
            ]
            if not_found:
                self._log_error(
                    "{}: Warning: Couldn't find ip_range for {}".format(
                        app_name, ",".join(not_found)
                    )
                )
                self.stdout.write(
                    "{}: Warning: Couldn't find ip_range for {}".format(
                        app_name, ",".join(not_found)
                    )
                )
            app_item["normalised_ip_ranges"] = ",".join(ip_ranges)

    def _collect_apps_deploy_info(
        self, github_token, apps_info, audit_data_keys, app_conf
    ):
        """
        To gain access to the github repo proves difficult than I thought,
        for now I will use the id_token from my login account, unless there is
        a need for frequent usage, then we need to implement device code flow

        The process of reading all those repo and exacting the fields from
        deploy.json is quite time consuming
        """
        github_api = GithubAPI(github_token)
        all_repos = github_api.get_all_repositories()
        for repo in all_repos:
            self.stdout.write("Reading repo {}....".format(repo.full_name))
            try:
                deployment_json = github_api.read_app_deploy_info(repo_instance=repo)
                if not deployment_json:
                    continue
                if repo.name in apps_info:
                    self.stdout.write("**Found deploy.json under this repo**")
                else:
                    self._log_error(
                        "{}: Found deploy.json under this repo, "
                        "but not registered in Control panel".format(repo.name)
                    )
                    self.stdout.write(
                        "**Found deploy.json under this repo, "
                        "but the app is not registered in Control panel **"
                    )

                self._add_new_app(apps_info, repo.name)
                apps_info[repo.name]["has_repo"] = True
                apps_info[repo.name]["deployment"] = deployment_json
                apps_info[repo.name]["auth"] = deepcopy(deployment_json)
                self._normalize_ip_ranges(
                    repo.name, apps_info[repo.name]["auth"], app_conf
                )
                audit_data_keys.extend(
                    [
                        key
                        for key in deployment_json.keys()
                        if key not in audit_data_keys
                    ]
                )
            except Exception as ex:
                self._log_error(
                    f"{repo.name}: Failed to load deploy.json due to the error: {str(ex)}"  # noqa: E501
                )
                self.stdout.write(
                    f"Failed to load deploy.json due to the error: {str(ex)}"
                )

    def _collect_apps_deployment_info(
        self, github_token, apps_info, audit_data_keys, app_conf
    ):
        github_api = GithubAPI(github_token, None)
        for app_name, app_info in apps_info.items():
            self.stdout.write("Reading repo {}....".format(app_info["repo_url"]))
            org_name, repo_name = extract_repo_info_from_url(app_info["repo_url"])
            try:
                github_api.github_org = org_name
                deployment_json = github_api.read_app_deploy_info(repo_name=repo_name)
                if not deployment_json:
                    continue

                app_info["has_repo"] = True
                app_info["deployment"] = deployment_json
                app_info["migration"]["ip_ranges"] = deployment_json.get("allowed_ip_ranges")
                app_info["migration"]["disable_authentication"] = \
                    deployment_json.get("disable_authentication") or False
                self._normalize_ip_ranges(app_name, app_info["migration"], app_conf)
                audit_data_keys.extend(
                    [
                        key
                        for key in deployment_json.keys()
                        if key not in audit_data_keys
                    ]
                )
            except Exception as ex:
                self._log_error(
                    f"{repo_name}: Failed to load deploy.json due to the error: {str(ex)}"  # noqa: E501
                )
                self.stdout.write(
                    f"Failed to load deploy.json due to the error: {str(ex)}"
                )

    def _process_urls(self, callback_urls, domains_mapping):
        """A new set of callbacks will be added based on the domains_mappings,
        the old ones will be still kept"""
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

    def _construct_logout_urls(self, callback_urls):
        logout_urls = []
        for callback in callback_urls:
            callback_url = urlparse(callback)
            logout_urls.append(
                urlunparse(
                    (
                        callback_url.scheme,
                        callback_url.netloc,
                        "/logout",
                        None,
                        None,
                        None,
                    )
                )
            )
        return logout_urls

    def _process_application_name(self, app_name, name_pattern):
        """only a few pre-defined variables will be supported
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

    def _locate_app_name(self, client_name, apps_names):
        # not efficient but logic is simple and more flexible to make sure
        # we can locate the client_name from our registered apps, the name has
        # been formatted by applying lower() or possible changing "_" to "-"
        for app_name in apps_names:
            if (
                client_name == app_name
                or client_name == app_name.lower()
                or client_name == app_name.lower().replace("_", "-")
            ):
                return app_name
        return None

    def _collect_app_auth0_basic_info(self, auth0_instance, apps_info, app_conf):
        """
        The function to collect the auth0 information for an app
        """
        clients = auth0_instance.clients.get_all()
        clients_id_name_map = {}
        apps_names = apps_info.keys()
        for client in clients:
            app_name_key = self._locate_app_name(client["name"], apps_names)

            if app_name_key is None:
                continue
            self.stdout.write(
                "Reading app({})'s auth0 information....".format(client["name"])
            )
            self._remove_sensitive_fields(client)
            apps_info[app_name_key]["auth0_client"] = client
            clients_id_name_map[client["client_id"]] = app_name_key
        return clients_id_name_map

    def _collection_apps_auth0_connections(
        self, auth0_instance, apps_info, clients_id_name_map
    ):
        connections = auth0_instance.connections.get_all()
        for connection in connections:
            for enabled_client_id in connection["enabled_clients"] or []:
                client_name = clients_id_name_map.get(enabled_client_id)
                if not client_name:
                    continue

                if not apps_info[client_name]["auth0_client"].get("connections"):
                    apps_info[client_name]["auth0_client"]["connections"] = []
                apps_info[client_name]["auth0_client"]["connections"].append(
                    connection["name"]
                )
                apps_info[client_name]["migration"]["connections"].append(
                    connection["name"]
                )

    def _collection_app_parameters_store_info(self, apps_info, apps_conf):
        """
        Read all the existing parameters for an app from aws parameter store
        control panel database has the apps' parameters in the database.
        """
        parameters = Parameter.objects.all()
        aws_param_service = AWSParameterStore()
        for parameter in parameters:
            # derive the application name from the role_name
            app_name_in_role = parameter.role_name.replace("{}_app_".format(settings.ENV), "")
            app_name_key = self._locate_app_name(app_name_in_role, apps_info.keys())

            if not app_name_key:
                continue

            self.stdout.write(
                "Reading parameter, {}, for the app - {}".format(
                    parameter.name, app_name_key
                )
            )

            para_response = aws_param_service.get_parameter(parameter.name)
            if para_response and para_response.get("Parameter"):
                param_value = para_response["Parameter"]["Value"]
                apps_info[app_name_key]["parameters"][parameter.key] = param_value
                new_param_key = apps_conf["params"]["name_pattern"].format(param_name=parameter.key)
                apps_info[app_name_key]["migration"]["parameters"][new_param_key] = param_value
            else:
                self._log_error(f"{app_name_key}: Couldn't find {parameter.name} from aws")

    def _gather_apps_full_info(
        self, github_token, app_conf, apps_info, audit_data_keys
    ):
        auth0_instance = ExtendedAuth0()

        # self.stdout.write("1. Collecting the deployment information of each app from github")  # noqa: E501
        # self._collect_apps_deploy_info(github_token, apps_info, audit_data_keys, app_conf)  # noqa: E501

        self.stdout.write("1. Collecting the deployment information of each app from github")
        self._collect_apps_deployment_info(github_token, apps_info, audit_data_keys, app_conf)

        self.stdout.write("2. Collecting the auth0 client information of each app.")
        clients_id_name_map = self._collect_app_auth0_basic_info(
            auth0_instance, apps_info, app_conf
        )

        self.stdout.write(
            "3. Collecting the connections information of each app from auth0"
        )
        self._collection_apps_auth0_connections(
            auth0_instance, apps_info, clients_id_name_map
        )

        self.stdout.write(
            "4. Collecting the parameters of each from AWS parameter store"
        )
        self._collection_app_parameters_store_info(apps_info, app_conf)

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
        with open(output_file_name, "w") as f:
            json.dump(apps_info, f, indent=4)

    def _convert_list_to_str(self, value):
        if type(value) is list:
            return ",".join(value)
        if type(value) is bool:
            return "Y" if value else "N"
        else:
            return str(value)

    def _get_deployed_app_list(self, pods_csv_file):
        pods_list = []
        with open(pods_csv_file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=",")
            for row in csv_reader:
                if row[0].startswith("restart"):
                    continue
                app_name = "-".join(row[0].split("-")[:-3])
                if app_name not in pods_list:
                    pods_list.append(app_name)
        return pods_list

    def _save_app_info_as_csv(
        self, csv_file, deployed_pods_list, apps_info, audit_data_keys
    ):
        with open(csv_file, "w") as f:
            writer = csv.writer(f)
            writer.writerow(audit_data_keys)
            for app_name, app_item in apps_info.items():
                data_row = []
                for data_key in audit_data_keys:
                    if data_key in app_item:
                        data_row.append(self._convert_list_to_str(app_item[data_key]))
                    elif data_key in (app_item.get("auth0_client") or []):
                        data_row.append(
                            self._convert_list_to_str(
                                app_item["auth0_client"][data_key]
                            )
                        )
                    elif data_key in (app_item.get("deployment") or []):
                        data_row.append(
                            self._convert_list_to_str(app_item["deployment"][data_key])
                        )
                    elif data_key == "has_auth0":
                        data_row.append("Y" if app_item.get("auth0_client") else "N")
                    elif data_key == "has_deployment":
                        data_row.append("Y" if app_item.get("deployment") else "N")
                    elif data_key == "has_parameters":
                        data_row.append("Y" if app_item.get("parameters") else "N")
                    elif data_key == "deployed_on_alpha":
                        data_row.append(
                            "Y"
                            if app_name.lower().replace("_", "-") in deployed_pods_list
                            else "N"
                        )
                    elif data_key == "auth_connections":
                        auth_conn_str = self._convert_list_to_str(
                            (app_item.get("auth0_client") or {}).get("connections", [])
                        )
                        data_row.append(auth_conn_str)
                    else:
                        data_row.append("")
                        continue

                writer.writerow(data_row)

    def _sanity_check_for_deployed_apps(self, apps_info, deployed_pods_list):
        app_names = list(apps_info.keys())
        app_names.extend([app_name.lower() for app_name in apps_info.keys()])
        app_names.extend(
            [app_name.lower().replace("_", "-") for app_name in apps_info.keys()]
        )
        mysterious_apps = set(deployed_pods_list) - set(app_names)
        if list(mysterious_apps):
            self._log_error(
                f"{','.join(list(mysterious_apps))} have no any information from db, "
                f"auth0 and repos having deploy.json"
            )

    def _default_log_file(self):
        return "./migration_script_errors_{}.log".format(int(time()))

    def _get_pre_defined_app_list(self, chosen_apps_file):
        """ assumption the csv include app_name and list of envs we want to initialise"""
        apps_scope = {}
        with open(chosen_apps_file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=",")
            next(csv_reader)
            for row in csv_reader:
                has_done = False
                if len(row) >= 6:
                    has_done = row[5].strip().lower() == "done"
                if has_done:
                    continue

                app_name = row[0].strip()
                apps_scope[app_name] = {
                    "new_app_name": row[1].strip() or app_name,
                    "source_repo_url": row[2],
                    "repo_url": row[3],
                    "envs": row[4].split("|") or ["dev", "prod"],
                }
        return apps_scope

    def handle(self, *args, **options):
        app_conf = self._load_json_file(options.get("app_conf"))
        apps_scope = self._get_pre_defined_app_list(options.get("chosen_apps"))
        self._error_log_file_name = options.get("log") or self._default_log_file()
        apps_info = self._init_app_info(apps_scope)
        self._gather_apps_full_info(
            options["token"], app_conf, apps_info, self.AUDIT_DATA_KEYS
        )
        self._save_to_file(list(apps_info.values()), options["file"])

        # Process the pod csv to extract the list of apps which has been
        # deployed on alpha cluster
        deployed_pods_list = []
        if options.get("pods"):
            deployed_pods_list = self._get_deployed_app_list(options.get("pods"))
            self._sanity_check_for_deployed_apps(apps_info, deployed_pods_list)

        if options.get("oaudit"):
            self._save_app_info_as_csv(
                options.get("oaudit"), deployed_pods_list, apps_info, self.AUDIT_DATA_KEYS
            )
