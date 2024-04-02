# Standard library
import base64
import hashlib

# Third-party
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic.base import TemplateView
from mozilla_django_oidc.views import OIDCLogoutView
from oauthlib.common import generate_token

# First-party/Local
from controlpanel.frontend.views.accessibility import Accessibility
from controlpanel.frontend.views.auth import EntraIdAuthView

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
from controlpanel.frontend.views.task import TaskList
from controlpanel.frontend.views.tool import RestartTool, ToolList
from controlpanel.frontend.views.user import (
    EnableBedrockUser,
    ResetMFA,
    SetSuperadmin,
    UserDelete,
    UserDetail,
    UserList,
)
from controlpanel.oidc import OIDCLoginRequiredMixin, oauth


class IndexView(OIDCLoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_template_names(self):
        if not self.request.user.justice_email:
            return ["justice_email.html"]

        return [self.template_name]

    def get(self, request, *args, **kwargs):
        """
        If the user is a superuser display the home page (containing useful
        admin related links). Otherwise, redirect the user to the list of the
        tools they currently have available on the platform.
        """

        if request.user.is_superuser:
            return super().get(request, *args, **kwargs)

        # TODO add feature request check
        if not request.user.justice_email:
            return super().get(request, *args, **kwargs)

        # Redirect to the tools page.
        return HttpResponseRedirect(reverse("list-tools"))

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

class LogoutView(OIDCLogoutView):
    def get(self, request):
        return super().post(request)
