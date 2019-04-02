from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView

from controlpanel.frontend.views.app import (
    AppsList,
    AppDetail,
    CreateApp,
    DeleteApp,
    AddCustomers,
    RemoveCustomer,
    AddAdmin,
    RevokeAdmin,
)
from controlpanel.frontend.views.datasource import (
    BucketDetail,
    BucketList,
    WarehouseData,
    WebappData,
)
from controlpanel.frontend.views.tool import (
    ToolsList,
    DeployTool,
    RestartTool,
)
from controlpanel.frontend.views.user import (
    UserList,
    UserDetail,
)
from controlpanel.frontend.views.whats_new import WhatsNew


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"
