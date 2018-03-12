from django.conf import settings

from moj_analytics.auth0_client import (
    Auth0 as Auth0Client,
    AuthorizationAPI,
    Group,
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

    def get_group_members(self, app_name):
        group = self.authorization_api.get(Group(name=app_name))

        if group is None:
            return None

        return group.get_members()


auth0 = Auth0()
