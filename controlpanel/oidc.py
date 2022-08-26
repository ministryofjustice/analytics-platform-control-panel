import structlog
from urllib.parse import urlencode

from django.utils import timezone

from controlpanel.api.models import User
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponseRedirect
from django.urls import reverse
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

log = structlog.getLogger(__name__)


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

    def authenticate(self, request, **kwargs):
        """
        To avoid cloning and re-implementing the OIDC Backend authenticate
        method, this checks the output of that method, and calls the
        authentication_event hook if a user has been sucessfully implemented.
        """
        authenticated_user = super().authenticate(request, **kwargs)
        if authenticated_user:
            # User states that are allowed on non-EKS infra platforms. See the
            # api.models.user.User model for details of what these mean.
            valid_old_infra_states = [
                authenticated_user.VOID,
                authenticated_user.PENDING,
                authenticated_user.REVERTED,
            ]
            # Calling the authentication event will ensure the user is
            # correctly set up for the current infrastructure (including the
            # process of migrating the user from the old infra -> EKS).
            authenticated_user.authentication_event()
        return authenticated_user


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


class OIDCLoginRequiredMixin(LoginRequiredMixin):
    """Verify that the current user is (still) authenticated."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        current_seconds = timezone.now().timestamp()
        token_expiry_seconds = self.request.session.get('oidc_id_token_expiration')
        if token_expiry_seconds and \
                current_seconds > token_expiry_seconds:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
