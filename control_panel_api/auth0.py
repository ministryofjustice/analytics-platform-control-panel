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

    def get_group_members(self, app_name):
        group = self.authorization_api.get(Group(name=app_name))

        if group is None:
            return None

        return group.get_members()

    def add_group_member(self, group_name, email):
        group = self.authorization_api.get_or_create(Group(name=group_name))

        user = self.authorization_api.get(User(
            email=email,
        ))

        if user is None:
            user = self.management_api.create(User(
                connection='email',
                email=email,
                email_verified=True,
            ))

        group.add_users([{'user_id': user['user_id']}])

    def delete_group_member(self, group_name, user_id):
        group = self.authorization_api.get(Group(name=group_name))

        if group is None:
            return None

        group.delete_users([{'user_id': user_id}])


auth0 = Auth0()
