from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView
from mozilla_django_oidc.views import OIDCLogoutView

from controlpanel.frontend.views.app import (
    AdminAppList,
    AppList,
    AppDetail,
    CreateApp,
    DeleteApp,
    AddCustomers,
    RemoveCustomer,
    AddAdmin,
    RevokeAdmin,
    GrantAppAccess,
    UpdateAppAccess,
    RevokeAppAccess,
)
from controlpanel.frontend.views.datasource import (
    AdminBucketList,
    BucketDetail,
    BucketList,
    CreateDatasource,
    DeleteDatasource,
    GrantAccess,
    GrantPolicyAccess,
    RevokeAccess,
    UpdateAccessLevel,
    UpdateIAMManagedPolicyAccessLevel,
    RevokeIAMManagedPolicyAccess,
    WebappBucketList,
)
from controlpanel.frontend.views.policy import (
    AdminIAMManagedPolicyList,
    IAMManagedPolicyList,
    IAMManagedPolicyCreate,
    IAMManagedPolicyDelete,
    IAMManagedPolicyDetail,
    IAMManagedPolicyFormRoleList,
    IAMManagedPolicyRemoveUser,
)
from controlpanel.frontend.views.parameter import (
    AdminParameterList,
    ParameterList,
    ParameterCreate,
    ParameterDelete,
    ParameterFormRoleList,
)
from controlpanel.frontend.views.tool import (
    ToolList,
    DeployTool,
    UpgradeTool,
    RestartTool,
)
from controlpanel.frontend.views.user import (
    ResetMFA,
    SetSuperadmin,
    UserList,
    UserDelete,
    UserDetail,
)
from controlpanel.frontend.views.whats_new import WhatsNew


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"


class LogoutView(OIDCLogoutView):
    def get(self, request):
        return super().post(request)
