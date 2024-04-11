# Standard library
from django.conf import settings
# Third-party
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic.base import TemplateView
from mozilla_django_oidc.views import OIDCLogoutView

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
from controlpanel.oidc import OIDCLoginRequiredMixin, get_code_challenge, oauth


class IndexView(OIDCLoginRequiredMixin, TemplateView):
    template_name = "home.html"
    http_method_names = ["get", "post"]

    def get_template_names(self):
        """
        Returns the template to instruct users to authenticate with their Justice
        account, unless this has already been captured.
        """
        if not self.request.user.justice_email:
            return ["justice_email.html"]

        return [self.template_name]

    def get(self, request, *args, **kwargs):
        """
        If the user has not authenticated with their Justice account, displays page to
        ask them to authenticate, to allow us to capture their email address.
        If their Justice email has been captured, normal users are redirected to their
        tools. Superusers are displayed the home page (containing useful
        admin related links).
        """

        if request.user.is_superuser:
            return super().get(request, *args, **kwargs)

        if settings.features.justice_auth.enabled and not request.user.justice_email:
            return super().get(request, *args, **kwargs)

        # Redirect to the tools page.
        return HttpResponseRedirect(reverse("list-tools"))

    def post(self, request, *args, **kwargs):
        """
        Redirects user to authenticate with Azure EntraID.
        """
        if not settings.features.justice_auth.enabled and not request.user.is_superuser:
            return self.http_method_not_allowed(request, *args, **kwargs)

        redirect_uri = request.build_absolute_uri(reverse("entraid-auth"))
        return oauth.azure.authorize_redirect(
            request,
            redirect_uri,
            code_challenge=get_code_challenge(),
        )


class LogoutView(OIDCLogoutView):
    def get(self, request):
        return super().post(request)
