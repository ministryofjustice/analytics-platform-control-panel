# Standard library
import base64
import hashlib

# Third-party
import sentry_sdk
from authlib.common.security import generate_token
from authlib.integrations.django_client import OAuthError
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

# First-party/Local
from controlpanel.oidc import OIDCLoginRequiredMixin, oauth


class FrontPageView(OIDCLoginRequiredMixin, TemplateView):
    http_method_names = ["get", "post"]
    template_name = "frontpage.html"

    def get(self, request, *args, **kwargs):
        if self.request.user.justice_email:
            return HttpResponseRedirect(reverse("index"))
        return super().get(request, *args, **kwargs)

    def post(self, request):
        code_challenge = self._get_code_challenge()
        redirect_uri = request.build_absolute_uri(reverse("entraid-auth"))
        return oauth.azure.authorize_redirect(
            request,
            redirect_uri,
            code_challenge=code_challenge,
        )

    def _get_code_challenge(self):
        code_verifier = generate_token(64)
        digest = hashlib.sha256(code_verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


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
