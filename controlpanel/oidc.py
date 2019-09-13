import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponseRedirect
from django.urls import reverse
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

from controlpanel.api.models import User


log = logging.getLogger(__name__)


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

    def verify_claims(self, claims):
        return True


class StateMismatchHandler(OIDCAuthenticationCallbackView):

    def get(self, *args, **kwargs):
        try:
            return super().get(*args, **kwargs)
        except SuspiciousOperation as e:
            log.warning(f'Caught {e}: redirecting to login')
            return HttpResponseRedirect(settings.LOGIN_REDIRECT_URL_FAILURE)


def logout(request):
    params = urlencode({
        "returnTo": f"{request.scheme}://{request.get_host()}{reverse('index')}",
        "client_id": settings.OIDC_RP_CLIENT_ID,
    })
    return f"{settings.AUTH0['logout_url']}?{params}"
