# Standard library
import base64
from collections import defaultdict
from pathlib import Path

# Third-party
import sentry_sdk
import structlog
import yaml
from auth0.authentication.get_token import GetToken
from auth0.authentication.rest import RestClient
from auth0.management import ManagementClient
from auth0.management.core.api_error import ApiError
from auth0.management.core.parse_error import ParsingError
from auth0.management.types import UpdateEnabledClientConnectionsRequestContentItem
from auth0.management.types.user_identity_schema import UserIdentitySchema
from django.conf import settings
from jinja2 import Environment
from rest_framework.exceptions import APIException

log = structlog.getLogger(__name__)

# Auth0 Management API 'per_page' parameter used for pagination
# This is the maximum they'll allow:
# https://auth0.com/docs/product-lifecycle/deprecations-and-migrations/migrate-to-paginated-queries
PER_PAGE = 50

# This is the maximum they'll allow for group/members API
PER_PAGE_FOR_GROUP_MEMBERS = 25

# The default value for timeout in auth0.management is 5 seconds which will
# get ReadTimeOut error quite easily on Auth0 dev tenant when Control panel
# initialises the connection with it. In order to avoid this, a longer timeout
# is defined below as the default value for this app. This value will be passed
# down and overwrite the default 5 seconds when the API classes in Auth0
# package are created
DEFAULT_TIMEOUT = 20


class Auth0Error(APIException):
    status_code = 500
    default_code = "auth0_error"
    default_detail = "Error querying Auth0 API"


class ExtendedAuth0:
    DEFAULT_GRANT_TYPES = ["authorization_code", "client_credentials"]
    DEFAULT_APP_TYPE = "regular_web"
    M2M_APP_TYPE = "non_interactive"
    M2M_GRANT_TYPES = ["client_credentials"]

    DEFAULT_CONNECTION_OPTION = "email"

    def __init__(self, **kwargs):
        self.client_id = kwargs.get("client_id", settings.AUTH0["client_id"])
        self.client_secret = kwargs.get("client_secret", settings.AUTH0["client_secret"])
        self.domain = kwargs.get("domain", settings.AUTH0["domain"])
        self.app_domain = kwargs.get("domain", settings.APP_DOMAIN)
        self.audience = "https://{domain}/api/v2/".format(domain=self.domain)

        self._management = ManagementClient(
            domain=self.domain,
            client_id=self.client_id,
            client_secret=self.client_secret,
            timeout=DEFAULT_TIMEOUT,
        )

        self._init_mng_apis()
        self._init_authorization_extension_apis()

    def _init_mng_apis(self):
        self.connections = ExtendedConnections(self._management.connections)
        self.clients = ExtendedClients(self._management.clients)

    def _init_authorization_extension_apis(self):
        self.authorization_extension_url = settings.AUTH0["authorization_extension_url"]
        self._extension_token = self._access_token(
            audience=settings.AUTH0["authorization_extension_audience"]
        )
        self.roles = Roles(
            self.authorization_extension_url,
            self._extension_token,
            timeout=DEFAULT_TIMEOUT,
        )
        self.permissions = Permissions(
            self.authorization_extension_url,
            self._extension_token,
            timeout=DEFAULT_TIMEOUT,
        )
        self.groups = Groups(
            self.authorization_extension_url,
            self._extension_token,
            timeout=DEFAULT_TIMEOUT,
        )
        self.users = ExtendedUsers(
            self._management.users,
            self.authorization_extension_url,
            self._extension_token,
        )

    def _access_token(self, audience):
        get_token = GetToken(
            self.domain, client_id=self.client_id, client_secret=self.client_secret
        )
        try:
            token = get_token.client_credentials(audience)
        except ApiError as error:
            error_detail = f"Access token error: {self.client_id}, {self.domain}, {error}"
            log.error(error_detail)
            sentry_sdk.capture_exception(error)
            raise Auth0Error(error_detail) from error

        return token["access_token"]

    def _enable_connections_for_new_client(self, client_id, chosen_connections):
        """
        When an auth0 client is created, by default all the available connections
        are enabled for this client except those which is not used by any app.
        This way is quite annoying, it means we have to go through all those
        unchosen connections to diable the client from it, then enable nomis
        login if nomis login has been chosen
        """
        for connection in self.connections.get_all():
            if connection.name in chosen_connections:
                self.connections.enable_client(connection, client_id)

    def _create_custom_connection(self, app_name, connections):
        new_connections = []
        if type(connections) is list:
            connections = {item: {} for item in connections}
        for connection_name, user_inputs in connections.items():
            if connection_name not in ExtendedConnections.custom_connections():
                new_connections.append(connection_name)
                continue

            if "name" not in user_inputs:
                user_inputs["name"] = app_name
            new_connection_name = self.connections.create_custom_connection(
                connection_name=connection_name, input_values=user_inputs
            )
            new_connections.append(new_connection_name)
        return new_connections

    def setup_auth0_client(self, client_name, app_url_name=None, connections=None, app_domain=None):
        """
        parameters:
            connections:
                {
                    <connection_name>: {<user_inputs if need}
                }
        """
        if connections is None:
            connections = {self.DEFAULT_CONNECTION_OPTION: {}}
        new_connections = self._create_custom_connection(client_name, connections)
        app_url = "https://{}.{}".format(app_url_name or client_name, app_domain or self.app_domain)
        client = self.clients.create(
            name=client_name,
            callbacks=[f"{app_url}/callback"],
            allowed_origins=[app_url],
            app_type=ExtendedAuth0.DEFAULT_APP_TYPE,
            web_origins=[app_url],
            grant_types=ExtendedAuth0.DEFAULT_GRANT_TYPES,
            allowed_logout_urls=[app_url],
        )
        client_id = client.client_id

        view_app = self.permissions.create({"name": "view:app", "applicationId": client_id})
        role = self.roles.create({"name": "app-viewer", "applicationId": client_id})
        self.roles.add_permission(role, view_app["_id"])
        try:
            group = self.groups.create({"name": client_name})
        except ApiError:
            # celery fails to unpickle original exception, but not 100% sure why.
            # Seems to be because __reduce__  method is incorrect? Possible bug.
            # https://github.com/celery/celery/issues/6990#issuecomment-1433689294
            # TODO what should happen if group already exists? Raise new error and
            #  catch in the worker? e.g.:
            # raise Auth0Error(detail=exc.message, code=exc.error_code)
            # Or get the group ID and continue?
            group = {"_id": self.groups.get_group_id(client_name)}

        self.groups.add_role(group["_id"], role["_id"])

        self._enable_connections_for_new_client(client_id, chosen_connections=new_connections)
        return client, group

    def setup_m2m_client(self, client_name, scopes):
        client, created = self._get_or_create(
            self.clients.clients_client,
            {
                "name": client_name,
                "app_type": "non_interactive",
                "grant_types": ExtendedAuth0.M2M_GRANT_TYPES,
            },
        )
        if not created:
            return client

        try:
            kwargs = {
                "client_id": client.client_id,
                "scope": scopes,
                "audience": settings.OIDC_CPANEL_API_AUDIENCE,
            }
            self._management.client_grants.create(**kwargs)
        except ApiError as error:
            # if the client grant already exists, it will raise 409 error, so we can ignore it.
            # otherwise, raise the error
            if error.status_code != 409:
                self.clients.delete(id=client.client_id)
                raise Auth0Error(error.__str__(), code=error.status_code) from error

        return client

    def rotate_m2m_client_secret(self, client_id):
        try:
            return self.clients.rotate_secret(id=client_id)
        except ApiError as error:
            if error.status_code == 404:
                return None
            raise Auth0Error(error.__str__(), code=error.status_code) from error

    def add_group_members_by_emails(
        self, emails, user_options=None, group_id=None, group_name=None
    ):
        if user_options is None:
            user_options = {}
        user_ids = self.users.add_users_by_emails(emails, user_options=user_options)
        self.groups.add_group_members(user_ids=user_ids, group_id=group_id, group_name=group_name)
        return user_ids

    def add_dashboard_member_by_email(self, email, user_options=None):
        if user_options is None:
            user_options = {}

        try:
            user_ids = self.users.add_users_by_emails([email], user_options=user_options)
            self._management.roles.users.assign(id=settings.DASHBOARD_AUTH0_ROLE_ID, users=user_ids)
        except ApiError as e:
            raise Auth0Error() from e

    def remove_dashboard_role(self, email):
        user_id = self.users.get_user_id_by_email(email, "email")

        try:
            self._management.users.roles.delete(
                id=user_id, roles=[settings.DASHBOARD_AUTH0_ROLE_ID]
            )
        except ApiError as e:
            raise Auth0Error() from e

    def clear_up_group(self, group_id):
        """
        Deletes a group from the authorization API

        It also deletes all the roles associated with the
        group.

        NOTE: Roles in the Auth0 Authorization API are
        meant to be flexible and they could potentially
        be attached to different groups.
        However, in our use-case, each app has 1 group
        and each group has 1 role (`app-viewer`) and
        each role has 1 permission (`view:app`) so it's
        safe to delete all the associated roles/permissions.
        """
        if not self.groups.has_group_existed(group_id):
            return
        role_ids = []
        permission_ids = []

        roles = self.groups.get_group_roles(group_id=group_id)
        for role in roles:
            role_ids.append(role["_id"])
            permission_ids.extend(role.get("permissions", []))

        # The group needs to be removed first in order to remove the roles
        # and permissions
        self.groups.delete(group_id)
        for role_id in role_ids:
            self.roles.delete(role_id)
        for permission_id in permission_ids:
            self.permissions.delete(permission_id)

    def clear_up_user(self, user_id):
        """
        In order to remove user from auth0 correctly, removing the user from
        related groups needs to be done first
        then remove user from auth0
        """
        if not self.users.has_existed(user_id):
            return

        groups = self.users.get_user_groups(user_id)
        for group in groups:
            self.groups.delete_group_members(user_ids=[user_id], group_id=group["_id"])
        self.users.delete_user(user_id)

    def clear_up_app(self, auth_client):
        client_id = auth_client.get("client_id")
        group_id = auth_client.get("group_id")
        if group_id:
            self.clear_up_group(group_id)
        if client_id:
            self.clients.delete(id=client_id)

    def get_client_enabled_connections(self, client_ids):

        if not client_ids:
            return {}
        enabled_connections = {}
        for client_id in client_ids:
            connection_names = self.clients.get_connection_names(id=client_id)
            if connection_names:
                enabled_connections[client_id] = connection_names
        return enabled_connections

    def update_client_auth_connections(
        self, app_name: str, client_id: str, new_conns: dict, existing_conns: list
    ):
        """
        There is no Auth0 API to get the list of enabled connection for a client,
        so we have to get all social connections, then check whether the client
        (client_id) is in the list of enabled_clients
        """
        connections = {self.DEFAULT_CONNECTION_OPTION: {}} if new_conns is None else new_conns
        new_connections = self._create_custom_connection(app_name, connections)

        client_connections = {
            conn.name: conn for conn in self.clients.get_connections(id=client_id)
        }

        # Get the list of  removed connections based on the existing connections
        removed_connections = list(set(existing_conns) - set(new_connections))
        real_new_connections = list(set(new_connections) - set(existing_conns))

        for name in removed_connections:
            if name in client_connections:
                self.connections.disable_client(client_connections[name], client_id)

        if real_new_connections:
            all_conns = {conn.name: conn for conn in self.connections.get_all()}
            for name in real_new_connections:
                if name not in client_connections and name in all_conns:
                    self.connections.enable_client(all_conns[name], client_id)

    def _get_or_create(self, client, resource):
        for item in client.list():
            item_dict = item.model_dump()

            if all(pair in item_dict.items() for pair in resource.items()):
                return item, False

        result = client.create(**resource)
        return result, True


class Auth0API(object):
    def __init__(self, domain, token, telemetry=True, timeout=5.0):
        self.domain = domain
        self.client = RestClient(jwt=token, telemetry=telemetry, timeout=timeout)
        self.no_pagination = True

    def _url(self, id=None, resource_name=None):
        endpoint = "{}".format(self.__class__.__name__.lower())
        url = "{}/{}".format(self.domain, endpoint)
        if id is not None:
            url = "{}/{}".format(url, id)
        if resource_name is not None:
            url = "{}/{}".format(url, resource_name)
        return url

    def all(self, request_url=None, fields=None, page=None, per_page=None, extra_params=None):
        params = extra_params or {}
        params["fields"] = fields and ",".join(fields) or None
        params["page"] = page
        params["per_page"] = per_page
        return self.client.get(request_url or self._url(), params=params)

    def pre_process_body(self, body):
        if "description" not in body and "name" in body:
            body["description"] = body["name"]

    def create(self, body):
        self.pre_process_body(body)
        return self.client.post(self._url(), data=body)

    def get(self, id, fields=None, include_fields=True):
        params = {"fields": fields and ",".join(fields) or None}
        if include_fields:
            params.update({"include_fields": str(include_fields).lower()})

        return self.client.get(self._url(id), params=params)

    def delete(self, id):
        return self.client.delete(self._url(id))

    def update(self, id, body):
        return self.client.patch(self._url(id), data=body)

    def put(self, id, body):
        return self.client.put(self._url(id), data=body)


class ExtendedAPIMethods(object):
    def all(
        self,
        request_url=None,
        fields=None,
        include_fields=True,
        page=None,
        per_page=None,
        extra_params=None,
    ):
        params = extra_params or {}
        params["fields"] = fields and ",".join(fields) or None
        params["include_fields"] = str(include_fields).lower()
        params["page"] = page
        params["per_page"] = per_page

        return self.client.get(request_url or self._url(), params=params)

    def _get_request_endpoint(self, endpoint=None):
        class_endpoint = None
        if hasattr(self, "endpoint"):
            class_endpoint = self.endpoint
        return endpoint or class_endpoint or "{}".format(self.__class__.__name__.lower())

    def _has_pagination_option(self):
        return not (hasattr(self, "no_pagination") and self.no_pagination)

    def _get_pagination_params(self):
        # pagination is optional as different APIs may not support it
        # e.g. Authorization extension API (except group/members) doesn't
        # support `page`/`per_page` params and it would respond with
        # a `400 BAD REQUEST` if these are passed.
        # plus the page is in general Zero based
        return {"include_totals": "true"}, 0, PER_PAGE

    def get_all(self, request_url=None, endpoint=None, has_pagination=False):
        items = []
        total = None
        params = None
        endpoint = self._get_request_endpoint(endpoint=endpoint)

        page_number = None
        per_page = None
        has_pagination_option = has_pagination or self._has_pagination_option()
        if has_pagination_option:
            params, page_number, per_page = self._get_pagination_params()

        while True:
            response = self.all(
                request_url=request_url,
                page=page_number,
                per_page=per_page,
                extra_params=params,
            )

            if "total" not in response:
                raise Auth0Error(f"get_all {endpoint}: Missing 'total' property")
            if endpoint not in response:
                raise Auth0Error(f"get_all {endpoint}: Missing '{endpoint}' property")
            if total is None:
                total = response["total"]
            if total != response["total"]:
                raise Auth0Error(f"get_all {endpoint}: Total changed")
            items.extend(response[endpoint])

            if not has_pagination_option:
                break
            if len(items) >= total:
                break
            if len(response[endpoint]) < 1:
                break
            page_number += 1

        return items

    def search_first_match(self, resource):
        resources = self.get_all()
        for other in resources:
            if all(pair in other.items() for pair in resource.items()):
                return other
        return None

    def get_or_create(self, resource):
        result = self.search_first_match(resource)
        created = False
        if result is None:
            result = self.create(resource)
            created = True
        return result, created


class ExtendedClients:
    endpoint = "clients"

    def __init__(
        self,
        clients_client,
    ):
        self.clients_client = clients_client

    def get(self, id):
        return self.clients_client.get(id=id)

    def get_all(self):
        return self.clients_client.list()

    def create(self, **kwargs):
        return self.clients_client.create(**kwargs)

    def delete(self, id):
        return self.clients_client.delete(id=id)

    def rotate_secret(self, id):
        return self.clients_client.rotate_secret(id=id)

    def get_connections(self, id):
        return self.clients_client.connections.get(id=id)

    def get_connection_names(self, id):
        connections = self.get_connections(id)
        connection_names = [conn.name for conn in connections]
        return connection_names


class ExtendedConnections:
    endpoint = "connections"

    def __init__(
        self,
        connections_client,
    ):
        self.connections_client = connections_client

    @staticmethod
    def custom_connections():
        return (settings.CUSTOM_AUTH_CONNECTIONS or "").split()

    def get_all(self):
        return self.connections_client.list()

    def get_enabled_clients(self, connection):
        result = []
        enabled_clients = self.connections_client.clients.get(id=connection.id)

        for client in enabled_clients:
            result.append(client.client_id)
        return result

    def disable_client(self, connection, client_id):
        try:
            self.connections_client.clients.update(
                id=connection.id,
                request=[
                    UpdateEnabledClientConnectionsRequestContentItem(
                        client_id=client_id,
                        status=False,
                    )
                ],
            )
        except ApiError as e:
            raise Auth0Error() from e

    def enable_client(self, connection, client_id):
        try:
            self.connections_client.clients.update(
                id=connection.id,
                request=[
                    UpdateEnabledClientConnectionsRequestContentItem(
                        client_id=client_id,
                        status=True,
                    )
                ],
            )
        except ApiError as e:
            raise Auth0Error() from e

    def _get_template_path_for_custom_connection(self, connection_name: str):
        return Path(__file__).parents[0] / Path("auth0_conns") / Path(connection_name)

    def get_all_connection_names(self):
        connections = self.get_all()
        connection_names = [connection.name for connection in connections]
        connection_names.extend(ExtendedConnections.custom_connections())
        return connection_names

    def _get_default_settings_for_custom_connection(self, connection_name, input_values):
        input_values["gateway_url"] = ""
        if hasattr(settings, "{}_gateway_url".format(connection_name).upper()):
            input_values["gateway_url"] = getattr(
                settings, "{}_gateway_url".format(connection_name).upper()
            )

    def create_custom_connection(self, connection_name: str, input_values: dict):
        """
        This method is only used to create custom connections which has
        configuration file within this repo
        """
        jinja_env = Environment()
        jinja_env.filters["base64enc"] = lambda x: base64.urlsafe_b64encode(
            x.encode("utf8")
        ).decode()

        # render the scripts
        template_path = self._get_template_path_for_custom_connection(connection_name)
        scripts = template_path.glob("*.js")
        script_templates = {
            x.stem: jinja_env.from_string(x.open(encoding="utf8").read()) for x in scripts
        }
        scripts_rendered = {}
        self._get_default_settings_for_custom_connection(connection_name, input_values)
        for name, script_template in script_templates.items():
            scripts_rendered[name] = script_template.render(**input_values)

        # render the main connection template
        with (template_path / Path("config.yaml")).open("r") as config_yaml_file:
            yaml_rendered = jinja_env.from_string(config_yaml_file.read()).render(**input_values)
            body = yaml.safe_load(yaml_rendered) or defaultdict(dict)
            body["options"]["scripts"] = scripts_rendered

        try:
            self.connections_client.create(**body)
        except ApiError as error:
            # Skip the exception when the connection name existed already
            if error.status_code != 409:
                raise Auth0Error(error.__str__(), code=error.status_code) from error
        return input_values["name"]


class ExtendedUsers:
    endpoint = "users"

    def __init__(self, users_client, auth_extension_url, auth_extension_token):
        self.users_client = users_client
        self.auth_extension_users = AuthExtensionUsers(auth_extension_url, auth_extension_token)

    def get(self, id):
        try:
            return self.users_client.get(id=id)
        except ParsingError as e:
            # Workaround for auth0-python v5 Pydantic validation bug
            # where identities[].user_id comes back as int instead of string
            if "identities" in str(e) and "user_id" in str(e):
                try:
                    raw_body = e.body
                    if isinstance(raw_body, dict) and "identities" in raw_body:
                        # Fix: convert all integer user_id values to strings
                        for identity in raw_body.get("identities", []):
                            if isinstance(identity, dict) and "user_id" in identity:
                                identity["user_id"] = str(identity["user_id"])

                        return raw_body
                except Exception as fix_error:
                    log.error("Failed to apply identities workaround", error=fix_error)
                    raise e from fix_error

            # Re-raise if it's a different error
            raise

    def get_all(self):
        return self.users_client.list()

    def create_user(self, email, email_verified=False, **kwargs):
        if "nickname" not in kwargs:
            kwargs["nickname"], _, _ = email.partition("@")

        try:
            response = self.users_client.create(
                email=email, email_verified=email_verified, **kwargs
            )
        except ApiError as e:
            raise Auth0Error("create_user", response) from e

        return response

    def delete_user(self, id):

        try:
            response = self.users_client.delete(id=id)
        except ApiError as e:
            raise Auth0Error("delete_user", response) from e
        return response

    def reset_mfa(self, id):
        provider = "google-authenticator"

        try:
            response = self.users_client.multifactor.delete_provider(id=id, provider=provider)
        except ApiError as e:
            raise Auth0Error("reset_mfa", response) from e

        return response

    def get_users_email_search(self, email, connection=None):
        """
        As the search performed here is based on the email, the results
        returned from this call won't be many especially if the connection is
        specified as well. it should be within default page-size (50 right now)
        so there is no pagination related param being passed into list() call.
        """
        query_string = f'email:"{email.lower()}"'
        search_engine = "v3"
        if connection:
            query_string = f'{query_string} AND identities.connection:"{connection}"'

        try:
            response = self.users_client.list(q=query_string, search_engine=search_engine)
        except ApiError as e:
            raise Auth0Error("get_users_email_search", response) from e

        return response.items

    def get_user_id_by_email(self, email, connection=None):
        response = self.get_users_email_search(email, connection)
        if response:
            return response[0].user_id
        return None

    def add_users_by_emails(self, emails, user_options=None):
        if user_options is None:
            user_options = {}
        user_ids_to_add = []

        for email in emails:
            lookup_response = self.get_users_email_search(email=email, connection="email")
            if lookup_response:
                user_ids_to_add.append(lookup_response[0].user_id)
            else:
                user_ids_to_add.append(
                    self.create_user(email=email, email_verified=True, **user_options).user_id
                )
        return user_ids_to_add

    def get_user_groups(self, user_id):
        return self.auth_extension_users.get_user_groups(user_id)

    def has_existed(self, user_id):
        query_string = f'user_id:"{user_id}"'

        try:
            response = self.users_client.list(q=query_string, search_engine="v3")
        except ApiError as e:
            raise Auth0Error("get_users_email_search", response) from e

        return len(response.items) > 0

    def remove_role(self, user_id, role_id):
        try:
            response = self.users_client.roles.delete(id=user_id, roles=[role_id])

            return response
        except ApiError as e:
            sentry_sdk.capture_exception(e)
            raise Auth0Error("remove_role", response) from e


class AuthExtensionUsers(Auth0API, ExtendedAPIMethods):
    endpoint = "users"

    def get_user_groups(self, user_id):
        request_url = "{}/users/{}/groups".format(self.domain, user_id)
        return self.all(request_url=request_url)


class Permissions(Auth0API, ExtendedAPIMethods):
    def pre_process_body(self, body):
        super(Permissions, self).pre_process_body(body)
        body["applicationType"] = "client"


class Roles(Auth0API, ExtendedAPIMethods):
    def pre_process_body(self, body):
        super(Roles, self).pre_process_body(body)
        body["applicationType"] = "client"

    def add_permission(self, role, permission_id):
        permissions = role.get("permissions") or []
        if permission_id in permissions:
            return
        else:
            permissions.append(permission_id)
            self.put(
                role["_id"],
                body={
                    "name": role["name"],
                    "description": role["description"],
                    "applicationId": role["applicationId"],
                    "applicationType": role["applicationType"],
                    "permissions": permissions,
                },
            )


class Groups(Auth0API, ExtendedAPIMethods):
    def add_role(self, id, role_id):
        self.client.patch(self._url(id, "roles"), data=[role_id])

    def get_group_id(self, group_name):
        group = self.search_first_match({"name": group_name})
        if not group:
            return None
        else:
            return group.get("_id")

    def _get_pagination_params(self):
        # All the auth extension APIs doesn't have page parameter but the API
        # for group's members does and the maximum value of per_page is 25, not
        # like other APIs which is 50, and it does not allow
        # include_totals parameter. It will return `400: "include_totals" is
        # not allowed` if this param is passed.
        # plus page parameter is One-based
        # https://auth0.com/docs/api/authorization-extension#get-group-members
        return None, 1, PER_PAGE_FOR_GROUP_MEMBERS

    def get_group_members_paginated(self, group_id, page=1, per_page=25):
        """
        gets members based on page number
        There is a maximum limit of 25 entries per page for customers
        """
        request_url = self._url(group_id, "members")
        response = self.all(request_url=request_url, page=page, per_page=per_page)
        return response

    def get_group_members(self, group_id):
        if group_id:
            return self.get_all(
                request_url=self._url(group_id, "members"),
                endpoint="users",
                has_pagination=True,
            )
        else:
            return []

    def get_group_roles(self, group_name=None, group_id=None):
        if group_id is None and group_name is None:
            raise Auth0Error("get_group_roles", "Please specify either group_id or group_name.")

        if group_id is None:
            group_id = self.get_group_id(group_name)
        if group_id:
            return self.all(request_url=self._url(group_id, "roles"))
        else:
            return []

    def add_group_members(self, user_ids, group_id=None, group_name=None):
        group_id = group_id or self.get_group_id(group_name)
        if not group_id:
            raise Auth0Error("Group for the app not found, was the app released?")
        response = self.client.patch(self._url(group_id, "members"), data=user_ids)

        if "error" in response:
            raise Auth0Error("add_group_members", response)

    def delete_group_members(self, user_ids, group_id):
        response = self.client.delete(
            self._url(group_id, "members"),
            data=user_ids,
        )
        if "error" in response:
            raise Auth0Error("delete_group_members", response)

    def has_group_existed(self, group_id):
        try:
            self.get(group_id, include_fields=False)
            return True
        except ApiError as error:
            if "does not exist" in error.__str__():
                return False
            else:
                raise error
