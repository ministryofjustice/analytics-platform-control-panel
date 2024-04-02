# Standard library

# Third-party
import sentry_sdk
from authlib.integrations.django_client import OAuthError
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import View

# First-party/Local
from controlpanel.oidc import OIDCLoginRequiredMixin, oauth


class EntraIdAuthView(OIDCLoginRequiredMixin, View):
    """
    This view is used as the callback after a user authenticates with their Justice
    identity via Azure EntraID, in order to capture a users Justice email address.
    """
    http_method_names = ["get"]

    def _authorize_token(self):
        """
        Attempts to valiate and return the access token
        """
        try:
            token = oauth.azure.authorize_access_token(self.request)
        except OAuthError as error:
            sentry_sdk.capture_exception(error)
            token = None
        return token

    def get(self, request, *args, **kwargs):
        """
        Attempts to retrieve the auth token, and update the user.
        """
        token = self._authorize_token()
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
        email = token["userinfo"]["email"]
        self.request.user.justice_email = email
        self.request.user.save()
