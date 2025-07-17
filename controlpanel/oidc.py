# Standard library
import base64
import hashlib
from urllib.parse import urlencode

# Third-party
import structlog
from authlib.common.security import generate_token
from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

# First-party/Local
from controlpanel.api.models import JusticeDomain, User
from controlpanel.api.pagerduty import PagerdutyClient

log = structlog.getLogger(__name__)
pagerduty_client = PagerdutyClient()


class OIDCSubAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Authentication backend which matches users by their `sub` claim
    """

    def create_user(self, claims):
        user_details = {
            "pk": claims.get("sub"),
            "username": claims.get(settings.OIDC_FIELD_USERNAME),
            "email": claims.get(settings.OIDC_FIELD_EMAIL),
            "name": self.normalise_name(claims.get(settings.OIDC_FIELD_NAME)),
            "justice_email": self.get_justice_email(claims.get(settings.OIDC_FIELD_EMAIL)),
        }
        return User.objects.create(**user_details)

    def normalise_name(self, name):
        """
        Normalise name to be in the format "Firstname Lastname"
        """
        if "," in name:
            parts = [part.strip() for part in name.split(",")]
            name = " ".join(reversed(parts))
        return name

    def get_justice_email(self, email):
        """
        Check if the email uses a justice domain and return it if it does, otherwise return None
        """
        email_domain = email.split("@")[-1].lower()
        justice_domains = JusticeDomain.objects.values_list("domain", flat=True)
        if email_domain in justice_domains:
            return email
        return None

    def update_user(self, user, claims):
        # Update the non-key information to sync the user's info
        # with user profile from idp when the user's username is not changed.
        if user.username != claims.get(settings.OIDC_FIELD_USERNAME):
            return user

        if user.email != claims.get(settings.OIDC_FIELD_EMAIL):
            user.email = claims.get(settings.OIDC_FIELD_EMAIL)
            user.save()
        normalised_name = self.normalise_name(claims.get(settings.OIDC_FIELD_NAME))
        if user.name != normalised_name:
            user.name = normalised_name
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

    @property
    def success_url(self):

        if not self.user.justice_email:
            return reverse("index")

        return super().success_url


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
        context["broadcast_messages"] = (
            settings.BROADCAST_MESSAGE.split("|") if settings.BROADCAST_MESSAGE else []
        )

        display_service_info = False
        pagerduty_posts = pagerduty_client.get_status_page_posts(settings.PAGERDUTY_STATUS_ID)

        if pagerduty_posts is not None:
            display_service_info = True
            context["pagerduty_posts"] = pagerduty_posts

        context["display_service_info"] = display_service_info
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


def get_code_challenge():
    code_verifier = generate_token(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


oauth = OAuth()
oauth.register(name="azure", **settings.AUTHLIB_OAUTH_CLIENTS["azure"])
