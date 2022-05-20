import structlog

from collections import OrderedDict
from rest_framework.exceptions import APIException

from auth0.v3 import authentication, exceptions
from auth0.v3.management import Auth0
from auth0.v3.management.clients import Clients
from auth0.v3.management.connections import Connections
from auth0.v3.management.users import Users
from auth0.v3.management.rest import RestClient

from django.conf import settings


log = structlog.getLogger(__name__)

# Auth0 Management API 'per_page' parameter used for pagination
# This is the maximum they'll allow:
# https://auth0.com/docs/product-lifecycle/deprecations-and-migrations/migrate-to-paginated-queries
PER_PAGE = 50


class Auth0Error(APIException):
    status_code = 500
    default_code = "auth0_error"
    default_detail = "Error querying Auth0 API"


class ExtendedAuth0(Auth0):

    def __init__(self, **kwargs):
        self.client_id = kwargs.get("client_id", settings.AUTH0["client_id"])
        self.client_secret = kwargs.get(
            "client_secret", settings.AUTH0["client_secret"]
        )
        self.domain = kwargs.get("domain", settings.AUTH0["domain"])
        self.app_domain = kwargs.get("domain", settings.AUTH0["app_domain"])
        self.audience = "https://{domain}/api/v2/".format(domain=self.domain)

        self._init_mng_apis()
        self._init_authorization_extension_apis()

    def _init_mng_apis(self):
        self._token = self._access_token(audience=self.audience)
        super(ExtendedAuth0, self).__init__(self.domain, self._token)

        self.clients = ExtendedClients(self.domain, self._token)
        self.connections = ExtendedConnections(self.domain, self._token)

    def _init_authorization_extension_apis(self):
        self.authorization_extension_url = settings.AUTH0["authorization_extension_url"]
        self._extension_token = self._access_token(audience=settings.AUTH0["authorization_extension_audience"])
        self.roles = Roles(self.authorization_extension_url, self._extension_token)
        self.permissions = Permissions(self.authorization_extension_url, self._extension_token)
        self.groups = Groups(self.authorization_extension_url, self._extension_token)
        self.users = ExtendedUsers(self.domain, self._token, self.authorization_extension_url, self._extension_token)

    def _access_token(self, audience):
        get_token = authentication.GetToken(self.domain)
        try:
            token = get_token.client_credentials(
                self.client_id,
                self.client_secret,
                audience)
        except exceptions.Auth0Error as error:
            error_detail = f"Access token error: {self.client_id}, {self.domain}, {error}"
            log.error(error_detail)
            raise Auth0Error(error_detail)

        return token["access_token"]

    def _disable_all_connections(self, client_id, ignores=[]):
        ignore_ids = [connection["id"] for connection in ignores]
        connections = self.connections.get_all()
        for connection in connections:
            if connection["id"] in ignore_ids:
                continue
            if client_id in connection["enabled_clients"]:
                self.connections.disable_client(connection, client_id)

    def setup_auth0_client(self, app_name, connections=None):
        app_url = "https://{}.{}".format(app_name, self.app_domain)
        client = self.clients.get_or_create(
            dict(
                name=app_name,
                callbacks=[f"{app_url}/callback"],
                allowed_origins=[app_url],
                app_type="regular_web"
            )
        )
        client_id = client["client_id"]
        self.clients.update(client_id, body={"web_origins": [app_url]})

        connections = connections or ["email"]
        auth0_connections = [
            self.connections.search_first_match(dict(name=connection)) for connection in connections
        ]
        self._disable_all_connections(client_id, ignores=auth0_connections)

        view_app = self.permissions.get_or_create(dict(name="view:app", applicationId=client_id))
        role = self.roles.get_or_create(dict(name="app-viewer", applicationId=client_id))
        self.roles.add_permission(role, view_app["_id"])
        group = self.groups.get_or_create(dict(name=app_name))
        self.groups.add_role(group["_id"], role["_id"])

    def add_group_members_by_emails(self, group_name, emails, user_options={}):
        user_ids = self.users.add_users_by_emails(emails, user_options=user_options)
        self.groups.add_group_members(group_name, user_ids=user_ids)
        return user_ids

    def clear_up_group(self, group_name):
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

        group_id = self.groups.get_group_id(group_name)
        if group_id:
            role_ids = []
            permission_ids = []

            roles = self.groups.get_group_roles(group_id=group_id)
            for role in roles:
                role_ids.append(role["_id"])
                permission_ids.extend(role.get("permissions", []))

            # The group needs to be removed first in order to remove the roles and permissions
            self.groups.delete(group_id)
            for role_id in role_ids:
                self.roles.delete(role_id)
            for permission_id in permission_ids:
                self.permissions.delete(permission_id)

    def clear_up_user(self, user_id):
        """In order to remove user from auth0 correctly, removing the user from related groups needs to be done first
        then remove user from auth0
        """
        groups = self.users.get_user_groups(user_id)
        for group in groups:
            self.groups.delete_group_members(user_ids=[user_id], group_id=group["_id"])
        self.users.delete(user_id)

    def clear_up_app(self, app_name, group_name):
        self.clear_up_group(group_name=group_name)
        client = self.clients.search_first_match(dict(name=app_name))
        if client:
            self.clients.delete(client["client_id"])


class Auth0API(object):

    def __init__(self, domain, token, telemetry=True, timeout=5.0):
        self.domain = domain
        self.client = RestClient(jwt=token, telemetry=telemetry, timeout=timeout)
        self.no_pagination = True

    def _url(self, id=None, resource_name=None):
        endpoint = "{}".format(self.__class__.__name__.lower())
        url = '{}/{}'.format(self.domain, endpoint)
        if id is not None:
            url = '{}/{}'.format(url, id)
        if resource_name is not None:
            url = '{}/{}'.format(url, resource_name)
        return url

    def all(self, request_url=None, fields=None, page=None, per_page=None, extra_params=None):
        params = extra_params or {}
        params['fields'] = fields and ','.join(fields) or None
        params['page'] = page
        params['per_page'] = per_page

        return self.client.get(request_url or self._url(), params=params)

    def pre_process_body(self, body):
        if "description" not in body and "name" in body:
            body["description"] = body["name"]

    def create(self, body):
        self.pre_process_body(body)
        return self.client.post(self._url(), data=body)

    def get(self, id, fields=None, include_fields=True):
        params = {'fields': fields and ','.join(fields) or None,
                  'include_fields': str(include_fields).lower()}

        return self.client.get(self._url(id), params=params)

    def delete(self, id):
        return self.client.delete(self._url(id))

    def update(self, id, body):
        return self.client.patch(self._url(id), data=body)

    def put(self, id, body):
        return self.client.put(self._url(id), data=body)


class ExtendedAPIMethods(object):

    def all(self, request_url=None, fields=None, include_fields=True, page=None, per_page=None, extra_params=None):
        params = extra_params or {}
        params['fields'] = fields and ','.join(fields) or None
        params['include_fields'] = str(include_fields).lower()
        params['page'] = page
        params['per_page'] = per_page

        return self.client.get(request_url or self._url(), params=params)

    def _get_request_endpoint(self, endpoint=None):
        class_endpoint = None
        if hasattr(self, 'endpoint'):
            class_endpoint = self.endpoint
        return endpoint or class_endpoint or "{}".format(self.__class__.__name__.lower())

    def _has_pagination_option(self):
        return not (hasattr(self, 'no_pagination') and self.no_pagination)

    def get_all(self, request_url=None, endpoint=None):
        items = []
        total = None
        params = None
        endpoint = self._get_request_endpoint(endpoint=endpoint)

        # pagination is optional as different APIs may not support it
        # e.g. Authorization extension API doesn't support `page`/`per_page`
        # params and it would respond with a `400 BAD REQUEST` if these are
        # passed.
        page_number = None
        per_page = None
        has_pagination_option = self._has_pagination_option()
        if has_pagination_option:
            params = {"include_totals": "true"}
            page_number = 0
            per_page = PER_PAGE

        while True:
            response = self.all(request_url=request_url, page=page_number, per_page=per_page, extra_params=params)

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

    def get_or_create(self, resource):
        result = self.search_first_match(resource)

        if result is None:
            result = self.create(resource)
        return result


class ExtendedClients(ExtendedAPIMethods, Clients):
    endpoint = 'clients'


class ExtendedConnections(ExtendedAPIMethods, Connections):
    endpoint = 'connections'

    def disable_client(self, connection, client_id):
        if client_id in connection["enabled_clients"]:
            connection["enabled_clients"].remove(client_id)
            self.update(connection["id"], body={"enabled_clients": connection["enabled_clients"]})


class ExtendedUsers(ExtendedAPIMethods, Users):
    endpoint = 'users'

    def __init__(self, domain, token, auth_extension_url, auth_extension_token, telemetry=True, timeout=5.0):
        super(ExtendedUsers, self).__init__(domain, token, telemetry=telemetry, timeout=timeout)
        self.auth_extension_users = AuthExtensionUsers(auth_extension_url, auth_extension_token)

    def create_user(self, email, email_verified=False, **kwargs):
        if "nickname" not in kwargs:
            kwargs["nickname"], _, _ = email.partition('@')

        response = self.create({"email": email, "email_verified": email_verified, **kwargs})
        if "error" in response:
            raise Auth0Error("create_user", response)
        return response

    def reset_mfa(self, id):
        provider = "google-authenticator"
        response = self.delete_multifactor(id, provider)
        if "error" in response:
            raise Auth0Error("reset_mfa", response)

        return response

    def get_users_email_search(self, email, connection=None):
        """
        As the search performed here is based on the email, the results returned from this call won't be many
        especially if the connection is specified as well. it should be within default page-size (50 right now),
        so there is no pagination related param being passed into list() call.
        """
        query_string = f"email:\"{email.lower()}\""
        search_engine = "v2"
        if connection:
            query_string = f"{query_string} AND identities.connection:\"{connection}\""
        response = self.list(q=query_string, search_engine=search_engine)
        if "error" in response:
            raise Auth0Error("get_users_email_search", response)

        return response.get(self.endpoint, [])

    def add_users_by_emails(self, emails, user_options={}):
        user_ids_to_add = []

        for email in emails:
            lookup_response = self.get_users_email_search(email=email, connection="email")
            if lookup_response:
                user_ids_to_add.append(lookup_response[0]["user_id"])
            else:
                user_ids_to_add.append(self.create_user(
                    email=email, email_verified=True, **user_options
                ).get("user_id"))
        return user_ids_to_add

    def get_user_groups(self, user_id):
        return self.auth_extension_users.get_user_groups(user_id)


class AuthExtensionUsers(Auth0API, ExtendedAPIMethods):
    endpoint = 'users'

    def get_user_groups(self, user_id):
        request_url = '{}/users/{}/groups'.format(self.domain, user_id)
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
        self.client.patch(self._url(id, 'roles'), data=[role_id])

    def get_group_id(self, group_name):
        group = self.search_first_match(dict(name=group_name))
        return group.get("_id")

    def get_group_members(self, group_name):
        group_id = self.get_group_id(group_name)
        if group_id:
            return self.get_all(request_url=self._url(group_id, "members"), endpoint="users")
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

    def add_group_members(self, group_name, user_ids):
        group_id = self.get_group_id(group_name)
        if not group_id:
            raise Auth0Error("Group for the app not found, was the app released?")
        response = self.client.patch(self._url(group_id, "members"), data=user_ids)

        if "error" in response:
            raise Auth0Error("add_group_members", response)

    def delete_group_members(self, user_ids, group_name=None, group_id=None):
        if group_id is None and group_name is None:
            raise Auth0Error("delete_group_members", "Please specify either group_id or group_name.")

        if group_id is None:
            group_id = self.get_group_id(group_name)
        if group_id:
            response = self.client.delete(
                self._url(group_id, 'members'),
                data=user_ids,
            )
            if "error" in response:
                raise Auth0Error("delete_group_members", response)
