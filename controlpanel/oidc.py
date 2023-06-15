# Standard library
from urllib.parse import urlencode

# Third-party
import structlog
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

# First-party/Local
from controlpanel.api.models import User

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

    def update_user(self, user, claims):
        # Update the non-key information to sync the user's info
        # with user profile from idp when the user's username is not changed.
        if user.username != claims.get(settings.OIDC_FIELD_USERNAME):
            return user

        if user.email != claims.get(settings.OIDC_FIELD_EMAIL):
            user.email = claims.get(settings.OIDC_FIELD_EMAIL)
            user.save()
        if user.name != claims.get(settings.OIDC_FIELD_NAME):
            user.name = claims.get(settings.OIDC_FIELD_NAME)
            user.save()
        return user

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
            log.warning(f"Caught {e}: redirecting to login")
            return HttpResponseRedirect(settings.LOGIN_REDIRECT_URL_FAILURE)


def logout(request):
    params = urlencode(
        {
            "returnTo": f"{request.scheme}://{request.get_host()}{reverse('index')}",
            "client_id": settings.OIDC_RP_CLIENT_ID,
        }
    )
    return f"{settings.AUTH0['logout_url']}?{params}"


class OIDCLoginRequiredMixin(LoginRequiredMixin):
    """Verify that the current user is (still) authenticated."""

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context["broadcast_messages"] = settings.BROADCAST_MESSAGE.split("|")
        context["settings"] = settings
        return context

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        current_seconds = timezone.now().timestamp()
        token_expiry_seconds = self.request.session.get("oidc_id_token_expiration")
        if token_expiry_seconds and current_seconds > token_expiry_seconds:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
