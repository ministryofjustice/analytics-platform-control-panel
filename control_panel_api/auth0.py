from collections import OrderedDict

from django.conf import settings

from moj_analytics.auth0_client import (
    Auth0 as Auth0Client,
    AuthorizationAPI,
    Group,
    ManagementAPI,
    User,
)


class Auth0(object):
    def __init__(self):
        self.api = Auth0Client(
            settings.OIDC_CLIENT_ID,
            settings.OIDC_CLIENT_SECRET,
            settings.OIDC_DOMAIN
        )

    @property
    def authorization_api(self):
        if not hasattr(self.api, 'authorization'):
            self.api.access(AuthorizationAPI(
                settings.OIDC_AUTH_EXTENSION_URL,
                settings.OIDC_AUTH_EXTENSION_AUDIENCE,
            ))

        return self.api.authorization

    @property
    def management_api(self):
        if not hasattr(self.api, 'management'):
            self.api.access(ManagementAPI(
                settings.OIDC_DOMAIN,
            ))

        return self.api.management

    def get_group_members(self, group_name):
        group = self.authorization_api.get(Group(name=group_name))

        if group is None:
            return None

        return group.get_members()

    def add_group_members(self, group_name, emails, user_options={}):
        group = self.authorization_api.get(Group(name=group_name))

        all_users = self.authorization_api.get_all(User)
        user_lookup = {
            user['email']: user
            for user in all_users if 'email' in user}

        def has_options(user):
            return all(
                item in user.items()
                for item in user_options.items())

        # sorted users for easier testing
        users_to_add = OrderedDict()

        for email in emails:
            user = user_lookup.get(email)

            if user and has_options(user):
                users_to_add[email] = user

            else:
                users_to_add[email] = self.management_api.create(User(
                    email=email,
                    email_verified=True,
                    **user_options))

        group.add_users(list(users_to_add.values()))

    def delete_group_members(self, group_name, user_ids):
        group = self.authorization_api.get(Group(name=group_name))

        if group is None:
            return None

        group.delete_users([
            {'user_id': user_id}
            for user_id in user_ids])
