# Third-party
import base64
import hashlib

from authlib.common.security import generate_token
from authlib.integrations.django_client import OAuthError
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic.base import TemplateView, View
from mozilla_django_oidc.views import OIDCLogoutView

# First-party/Local
from controlpanel.frontend.views.accessibility import Accessibility

# isort: off
from controlpanel.frontend.views.app import (
    AddAdmin,
    AddCustomers,
    AdminAppList,
    AppDetail,
    AppList,
    CreateApp,
    DeleteApp,
    GrantAppAccess,
    RemoveCustomer,
    RemoveCustomerByEmail,
    RevokeAdmin,
    RevokeAppAccess,
    SetupAppAuth0,
    RemoveAppAuth0,
    UpdateAppAccess,
    UpdateAppAuth0Connections,
    UpdateAppIPAllowlists,
    RemoveAppDeploymentEnv,
)

# isort: on
# First-party/Local
from controlpanel.frontend.views.datasource import (
    AdminBucketList,
    BucketDetail,
    BucketList,
    CreateDatasource,
    DeleteDatasource,
    GrantAccess,
    GrantPolicyAccess,
    RevokeAccess,
    RevokeIAMManagedPolicyAccess,
    UpdateAccessLevel,
    UpdateIAMManagedPolicyAccessLevel,
    WebappBucketList,
)
from controlpanel.frontend.views.help import Help
from controlpanel.frontend.views.ip_allowlist import (
    IPAllowlistCreate,
    IPAllowlistDelete,
    IPAllowlistDetail,
    IPAllowlistList,
)
from controlpanel.frontend.views.login_fail import LoginFail
from controlpanel.frontend.views.policy import (
    AdminIAMManagedPolicyList,
    IAMManagedPolicyCreate,
    IAMManagedPolicyDelete,
    IAMManagedPolicyDetail,
    IAMManagedPolicyFormRoleList,
    IAMManagedPolicyList,
    IAMManagedPolicyRemoveUser,
)
from controlpanel.frontend.views.release import (
    ReleaseCreate,
    ReleaseDelete,
    ReleaseDetail,
    ReleaseList,
)
from controlpanel.frontend.views.reset import ResetHome
from controlpanel.frontend.views.tool import RestartTool, ToolList
from controlpanel.frontend.views.user import (
    ResetMFA,
    SetSuperadmin,
    EnableBedrockUser,
    UserDelete,
    UserDetail,
    UserList,
)
from controlpanel.oidc import OIDCLoginRequiredMixin, oauth
from controlpanel.frontend.views.task import TaskList


class IndexView(OIDCLoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get(self, request):
        """
        If the user is a superuser display the home page (containing useful
        admin related links). Otherwise, redirect the user to the list of the
        tools they currently have available on the platform.
        """
        if not request.user.justice_email:
            return HttpResponseRedirect(reverse("frontpage"))

        if request.user.is_superuser:
            return super().get(request)
        else:
            # Redirect to the tools page.
            return HttpResponseRedirect(reverse("list-tools"))


class FrontPageView(TemplateView):
    template_name = "frontpage.html"
    # TODO bypass when user has already authenticated with UserPassesTestMixin

    def _get_code_challenge(self):
        code_verifier = generate_token(64)
        digest = hashlib.sha256(code_verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    def post(self, request):
        code_challenge = self._get_code_challenge()
        redirect_uri = request.build_absolute_uri(reverse("entraid-auth"))
        return oauth.azure.authorize_redirect(
            request, redirect_uri, code_challenge=code_challenge,
        )


class EntraIdAuthView(View):

    def _authorize_token(self):
        try:
            token = oauth.azure.authorize_access_token(self.request)
        except OAuthError:
            # TODO log the error
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
            message=f"Successfully authenticated with your email {email}"
        )


class LogoutView(OIDCLogoutView):
    def get(self, request):
        return super().post(request)
