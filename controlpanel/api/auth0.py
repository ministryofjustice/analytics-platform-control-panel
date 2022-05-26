from collections import OrderedDict
from urllib import parse

import requests
from auth0.v3 import authentication, exceptions
from django.conf import settings
from rest_framework.exceptions import APIException


class Auth0Error(APIException):
    status_code = 500
    default_code = "auth0_error"
    default_detail = "Error querying Auth0 API"


class APIClient:
    base_url = None
    audience = None

    def __init__(self, **kwargs):
        self.client_id = kwargs.get("client_id", settings.AUTH0["client_id"])
        self.client_secret = kwargs.get(
            "client_secret", settings.AUTH0["client_secret"]
        )
        self.domain = kwargs.get("domain", settings.AUTH0["domain"])
        self._access_token = None

    @property
    def access_token(self):
        if self._access_token is None:
            get_token = authentication.GetToken(self.domain)

            try:
                token = get_token.client_credentials(
                    self.client_id, self.client_secret, self.audience
                )

            except exceptions.Auth0Error as error:
                raise Auth0Error(
                    f"Failed getting Auth0 access token for client "
                    f"{self.client_id} for audience {self.audience} "
                    f"at {self.domain}: {error}"
                )

            self._access_token = token["access_token"]

        return self._access_token

    def request(self, method, endpoint, raw=False, **kwargs):
        base_url = self.base_url
        if not base_url.endswith('/'):
            base_url = base_url + '/'
        url = f"{base_url}{endpoint}"
        response = requests.request(
            method,
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            **kwargs,
        )
        if not raw:
            response.raise_for_status()

            if response.text:
                return response.json()

            return {}
        else:
            return response

    def get_all(self, endpoint, key=None, **kwargs):
        items = []
        total = None
        if "params" not in kwargs:
            kwargs["params"] = {}
        if "page" in kwargs:
            kwargs["params"]["page"] = kwargs.pop("page")
        if "per_page" in kwargs:
            kwargs["params"]["per_page"] = kwargs.pop("per_page")

        if key is None:
            key = endpoint

        while True:
            response = self.request("GET", endpoint, **kwargs)

            if "total" not in response:
                raise Auth0Error(f"get_all {endpoint}: Missing total")

            if key not in response:
                raise Auth0Error(f"get_all {endpoint}: Missing key {key}")

            if total is None:
                total = response["total"]

            if total != response["total"]:
                raise Auth0Error(f"get_all {endpoint}: Total changed")

            items.extend(response[key])

            if len(items) >= total:
                break

            if len(response[key]) < 1:
                break

            if "page" not in kwargs["params"]:
                kwargs["params"]["page"] = 1

            kwargs["params"]["page"] += 1

        return items


class ManagementAPI(APIClient):
    base_url = f"https://{settings.AUTH0['domain']}/api/v2/"
    audience = base_url

    def create_user(self, email, email_verified=False, **kwargs):
        if "nickname" not in kwargs:
            kwargs["nickname"], _, _ = email.partition('@')

        response = self.request(
            "POST",
            "users",
            json={"email": email, "email_verified": email_verified, **kwargs},
        )

        if "error" in response:
            raise Auth0Error("create_user", response)

        return response

    def get_user(self, user_id):
        response = self.request("GET", f"users/{user_id}")

        if "error" in response:
            raise Auth0Error("get_user", response)

        return response

    def list_users(self, **kwargs):
        response = self.request("GET", "users", **kwargs)

        if "error" in response:
            raise Auth0Error("list_users", response)

        return response

    def reset_mfa(self, user_id):
        provider = "google-authenticator"
        response = self.request(
            "DELETE",
            f"users/{user_id}/multifactor/{provider}",
        )

        if "error" in response:
            raise Auth0Error("reset_mfa", response)

        return response

    def get_users_email_search(self, email, connection=None):
        query_string = f"email:\"{email.lower()}\""

        if connection:
            params = {
                "q": f"{query_string} AND identities.connection:\"{connection}\"",
                "search_engine":"v2",
            }
        else:
            params={
                "q":query_string,
                "search_engine":"v2",
            }

        response = self.request(
            "GET",
            "users",
            params=params,
        )

        if "error" in response:
            raise Auth0Error("get_users_email_search", response)

        return response


class AuthorizationAPI(APIClient):
    base_url = settings.AUTH0["authorization_extension_url"]
    audience = "urn:auth0-authz-api"

    def get_users(self):
        return self.get_all("users", page=0, per_page=100)

    def get_group(self, group_name):
        groups = [
            group for group in self.get_all("groups") if group["name"] == group_name
        ]

        if len(groups) != 1:
            return None

        return groups[0]

    def get_group_id(self, group_name):
        group = self.get_group(group_name)
        if group:
            return group["_id"]


    def delete_group(self, group_name):
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

        See Auth0 Authorization extension API docs:
        - https://auth0.com/docs/api/authorization-extension#get-group-roles
        - https://auth0.com/docs/api/authorization-extension#delete-group
        - https://auth0.com/docs/api/authorization-extension#delete-role
        - https://auth0.com/docs/api/authorization-extension#delete-permission
        """

        group_id = self.get_group_id(group_name)
        if group_id:
            role_ids = []
            permission_ids = []

            roles = self.request("GET", f"groups/{group_id}/roles")
            for role in roles:
                role_ids.append(role["_id"])
                permission_ids.extend(role.get("permissions", []))

            self.request("DELETE", f"groups/{group_id}")
            for role_id in role_ids:
                self.request("DELETE", f"roles/{role_id}")
            for permission_id in permission_ids:
                self.request("DELETE", f"permissions/{permission_id}")


    def get_group_members(self, group_name):
        group_id = self.get_group_id(group_name)
        if group_id:
            return self.get_all(
                f'groups/{group_id}/members', key="users", per_page=25
            )

    def add_group_members(self, group_name, emails, user_options={}):
        group_id = self.get_group_id(group_name)
        if not group_id:
            raise Auth0Error("Group for the app not found, was the app released?")

        users_to_add = OrderedDict()
        mgmt = ManagementAPI()

        for email in emails:
            lookup_response = mgmt.get_users_email_search(email=email, connection="email")
            if lookup_response:
                users_to_add[email] = lookup_response[0]
            else:
                users_to_add[email] = mgmt.create_user(
                    email=email, email_verified=True, **user_options
                )

        response = self.request(
            "PATCH",
            f'groups/{group_id}/members',
            json=[user["user_id"] for user in users_to_add.values()],
        )

        if "error" in response:
            raise Auth0Error("add_group_members", response)

        return users_to_add.values()

    def delete_group_members(self, group_name, user_ids):
        group_id = self.get_group_id(group_name)
        if group_id:
            response = self.request(
                "DELETE",
                f'groups/{group_id}/members',
                json=user_ids,
            )

            if "error" in response:
                raise Auth0Error("delete_group_members", response)
