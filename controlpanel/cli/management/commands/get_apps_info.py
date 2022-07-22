import json
import os
import csv
from urllib.parse import urlparse
from django.core.management.base import BaseCommand, CommandError

from controlpanel.api.github import GithubAPI
from controlpanel.api.auth0 import ExtendedAuth0
from controlpanel.api.aws import AWSParameters
from controlpanel.api.models import Parameter
from django.conf import settings


class Command(BaseCommand):

    """"
    This command line tool is to retrieve full information about an app hosted on AP
    The possible source of not missing any possible app is to reading through the github repos to get the key attributes
    defined in the deploy.json, then use the info as the base to gather the application info from auth0 and parameters
    from AWS parameters store. The outcome will be stored as json file.
    """
    help = "Retrieve all those information related to an app including github, auth0 and DB"

    def add_arguments(self, parser):
        parser.add_argument("-t", "--token", required=True, type=str,
                            help="The token for accessing the github")
        parser.add_argument("-f", "--file", required=True, type=str,
                            help="The path for storing the applications' information")
        parser.add_argument("-d", "--domain_conf", type=str,
                            help="The file of mapping old app domain to new domain")
        parser.add_argument("-od", "--odeploy", type=str,
                            help="The path of storing application's deployment information as csv")

    def _add_new_app(self, apps_info, app_name):
        if app_name not in apps_info:
            apps_info[app_name] = {
                "app_name": app_name,
                "deployment": {},
                "auth0_client": {},
                "parameters": {},
                "auth": {}
            }

    def _collect_apps_deploy_info(self, github_token, apps_info, deployment_keys):
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
                self._add_new_app(apps_info, repo.name)
                apps_info[repo.name]["old_deployment"] = deployment_json
                apps_info[repo.name]["auth"] = deployment_json

                deployment_keys.extend([key for key in deployment_json.keys() if key not in deployment_keys])
            except Exception as ex:
                self.stdout.write(f"Failed to load deploy.json due to the error: {str(ex)}")

    def _process_callbacks(self, callback_urls, domains_mapping):
        new_callback_urls = []
        for callback in callback_urls:
            app_domain = urlparse(callback).netloc
            new_app_domain = domains_mapping.get(app_domain) or app_domain
            new_callback_urls.append(callback.replace(app_domain, new_app_domain))
        return ", ".join(new_callback_urls)

    def _collect_app_auth0_basic_info(self, auth0_instance, apps_info, domains_mapping):
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

            apps_info[client['name']]["auth0_client"] = client
            apps_info[client['name']]["auth"]["client_id"] = client["client_id"],
            apps_info[client['name']]["auth"]["client_secret"] = client["client_secret"],
            apps_info[client['name']]["auth"]["callbacks"] = self._process_callbacks(
                client["callbacks"], domains_mapping)
            clients_id_name_map[client["client_id"]] = client['name']
        return clients_id_name_map

    def _collection_apps_auth0_connectons(self, auth0_instance, apps_info, clients_id_name_map):
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
        aws_param_service = AWSParameters()
        for parameter in parameters:
            # derive the application name from the role_name
            app_name = parameter.role_name.replace("{}_app_".format(settings.ENV), "")

            self.stdout.write("Reading parameter, {}, for the app - {}".format(parameter.name, app_name))

            self._add_new_app(apps_info, app_name)
            para_response = aws_param_service.get_parameter(parameter.name)
            apps_info[app_name]["parameters"][parameter.key] = para_response["Parameter"]["Value"]

    def _gather_apps_auth0_info(self, github_token, domains_mapping, apps_info, deployment_keys):
        auth0_instance = ExtendedAuth0()

        self.stdout.write("1. Collecting the deployment information of each app from github")
        self._collect_apps_deploy_info(github_token, apps_info, deployment_keys)

        self.stdout.write("2. Collecting the auth0 client information of each app.")
        clients_id_name_map = self._collect_app_auth0_basic_info(auth0_instance, apps_info, domains_mapping)

        self.stdout.write("3. Collecting the connections information of each app from auth0")
        self._collection_apps_auth0_connectons(auth0_instance, apps_info, clients_id_name_map)

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
            json.dump(apps_info, f)

    def _save_app_deployments_as_csv(self, csv_file, apps_info, deployment_keys):
        with open(csv_file, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(deployment_keys)
            deployment_keys.remove("app_name")
            for app_name, app_item in apps_info.items():
                deploy_info = app_item.get("old_deployment") or {}
                writer.writerow([app_name] + [deploy_info.get(key, "") for key in deployment_keys])

    def handle(self, *args, **options):
        domain_mapping = self._load_json_file(options.get("domain_conf"))
        apps_info = {}
        deployment_keys = ["app_name"]
        self._gather_apps_auth0_info(options["token"], domain_mapping, apps_info, deployment_keys)
        self._save_to_file(list(apps_info.values()), options["file"])

        if options.get('odeploy'):
            self._save_app_deployments_as_csv(options.get('odeploy'), apps_info, deployment_keys)
