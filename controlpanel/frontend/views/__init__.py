# Third-party
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic.base import TemplateView
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
    UserDelete,
    UserDetail,
    UserList,
)
from controlpanel.oidc import OIDCLoginRequiredMixin


class IndexView(OIDCLoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get(self, request):
        """
        If the user is a superuser display the home page (containing useful
        admin related links). Otherwise, redirect the user to the list of the
        tools they currently have available on the platform.
        """
        if request.user.is_superuser:
            return super().get(request)
        else:
            # Redirect to the tools page.
            return HttpResponseRedirect(reverse("list-tools"))


class LogoutView(OIDCLogoutView):
    def get(self, request):
        return super().post(request)
