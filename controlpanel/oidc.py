from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from controlpanel.api.models import User


class OIDCSubAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Authentication backend which matches users by their `sub` claim
    """

    def create_user(self, claims):
        return User.objects.create(
            pk=claims.get("sub"),
            username=claims.get(settings.OIDC_FIELD_USERNAME),
            email=claims.get(settings.OIDC_FIELD_EMAIL),
            name=claims.get(settings.OIDC_FIELD_NAME),
        )

    def filter_users_by_claims(self, claims):
        sub = claims.get("sub")
        if not sub:
            return self.UserModel.objects.none()

        try:
            return User.objects.filter(pk=sub)

        except User.DoesNotExist:
            return self.UserModel.objects.none()


def logout(request):
    params = urlencode({
        "returnTo": f"{request.scheme}://{request.get_host()}{reverse('index')}",
        "client_id": settings.OIDC_RP_CLIENT_ID,
    })
    return f"{settings.AUTH0['logout_url']}?{params}"
