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
    http_method_names = ["get"]

    def _authorize_token(self):
        try:
            token = oauth.azure.authorize_access_token(self.request)
        except OAuthError as error:
            sentry_sdk.capture_exception(error)
            token = None
        return token

    def get(self, request, *args, **kwargs):
        token = self._authorize_token()
        if not token:
            messages.error(self.request, "Something went wrong, please try again soon")
            return HttpResponseRedirect(reverse("index"))

        self.update_user(token=token)
        return HttpResponseRedirect(reverse("index"))

    def update_user(self, token):
        email = token["userinfo"]["email"]
        self.request.user.justice_email = email
        self.request.user.save()
        messages.success(
            request=self.request,
            message=f"Successfully authenticated with your email {email}",
        )
