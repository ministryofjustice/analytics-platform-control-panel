from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView

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
    RevokeAppAccess,
)
from controlpanel.frontend.views.datasource import (
    AdminBucketList,
    BucketDetail,
    BucketList,
    CreateDatasource,
    DeleteDatasource,
    GrantAccess,
    RevokeAccess,
    UpdateAccessLevel,
    WebappBucketList,
)
from controlpanel.frontend.views.parameter import (
    AdminParameterList,
    ParameterList,
    ParameterCreate,
    ParameterDelete,
    ParameterFormRoleList,
)
from controlpanel.frontend.views.tool import (
    ToolsList,
    DeployTool,
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
