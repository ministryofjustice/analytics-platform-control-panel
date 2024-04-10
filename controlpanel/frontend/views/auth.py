# Standard library

# Third-party
import sentry_sdk
import structlog
from authlib.integrations.django_client import OAuthError
from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.views import View

# First-party/Local
from controlpanel.oidc import OIDCLoginRequiredMixin, oauth

log = structlog.getLogger(__name__)


class EntraIdAuthView(OIDCLoginRequiredMixin, View):
    """
    This view is used as the callback after a user authenticates with their Justice
    identity via Azure EntraID, in order to capture a users Justice email address.
    """
    http_method_names = ["get"]

    def _get_access_token(self):
        """
        Attempts to valiate and return the access token
        """
        try:
            token = oauth.azure.authorize_access_token(self.request)
        except OAuthError as error:
            sentry_sdk.capture_exception(error)
            log.error(error.description)
            token = None
        return token

    def get(self, request, *args, **kwargs):
        """
        Attempts to retrieve the auth token, and update the user.
        """
        if not settings.features.justice_auth.enabled and not request.user.is_superuser:
            raise Http404()

        token = self._get_access_token()
        if not token:
            messages.error(request, "Something went wrong, please try again")
            return HttpResponseRedirect(reverse("index"))

        self.update_user(token=token)
        messages.success(
            request=request,
            message=f"Successfully authenticated with your email {request.user.justice_email}",
        )
        return HttpResponseRedirect(reverse("index"))

    def update_user(self, token):
        """
        Update user with details from the ID token returned by the provided EntraID
        access token
        """
        self.request.user.justice_email = token["userinfo"]["email"]
        self.request.user.azure_oid = token["userinfo"]["oid"]
        self.request.user.save()
