from collections import OrderedDict

from auth0.v3 import authentication, exceptions
from django.conf import settings
import requests
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

    def request(self, method, endpoint, **kwargs):
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
        response.raise_for_status()

        if response.text:
            return response.json()

        return {}

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

    def get_group_members(self, group_name):
        group = self.get_group(group_name)
        if group:
            return self.get_all(
                f'groups/{group["_id"]}/members', key="users", per_page=25
            )

    def add_group_members(self, group_name, emails, user_options={}):
        group = self.get_group(group_name)
        mgmt = ManagementAPI()
        users = self.get_users()
        user_lookup = {user["email"]: user for user in users if "email" in user}

        def has_options(user):
            for identity in user["identities"]:
                if all(item in identity.items() for item in user_options.items()):
                    return True

        users_to_add = OrderedDict()

        for email in emails:
            user = user_lookup.get(email)

            if user and has_options(user):
                users_to_add[email] = user

            else:
                users_to_add[email] = mgmt.create_user(
                    email=email, email_verified=True, **user_options
                )

        response = self.request(
            "PATCH",
            f'groups/{group["_id"]}/members',
            json=[user["user_id"] for user in users_to_add.values()],
        )

        if "error" in response:
            raise Auth0Error("add_group_members", response)

        return users_to_add.values()

    def delete_group_members(self, group_name, user_ids):
        group = self.get_group(group_name)
        if group is None:
            return None

        response = self.request(
            "DELETE", f'groups/{group["_id"]}/members', json=user_ids
        )

        if "error" in response:
            raise Auth0Error("delete_group_members", response)


class ManagementAPI(APIClient):
    base_url = f"https://{settings.AUTH0['domain']}/api/v2/"
    audience = base_url

    def create_user(self, email, email_verified=False, **kwargs):
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

    def list_users(self):
        response = self.request("GET", "users")

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
