from django.contrib.auth.models import Group
from rest_framework import viewsets

from control_panel_api.filters import (
    AppFilter,
    UserFilter,
)
from control_panel_api.models import App, User
from control_panel_api.permissions import (
    AppPermissions,
    UserPermissions,
)
from control_panel_api.serializers import (
    GroupSerializer,
    AppSerializer,
    UserSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = (UserFilter,)
    permission_classes = (UserPermissions, )


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class AppViewSet(viewsets.ModelViewSet):
    queryset = App.objects.all()
    serializer_class = AppSerializer
    filter_backends = (AppFilter,)
    permission_classes = (AppPermissions, )
