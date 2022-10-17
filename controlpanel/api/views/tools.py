# Third-party
from django.conf import settings
from rest_framework import mixins, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

# First-party/Local
from controlpanel.api import permissions
from controlpanel.api.github import GithubAPI
from controlpanel.api.models import Tool
from controlpanel.api.serializers import GithubItemSerializer, ToolSerializer


class ToolViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    filter_backends = []
    model = Tool
    pagination_class = None
    permission_classes = (permissions.ToolPermissions,)
    serializer_class = ToolSerializer


class RepoApi(GenericAPIView):
    serializer_class = GithubItemSerializer
    permission_classes = (permissions.AppPermissions,)
    action = "retrieve"

    def get_queryset(self):
        return []

    def query(self, org: str, page: int):
        token = self.request.user.github_api_token
        repos = GithubAPI(token).get_repos(org, page)

        if not isinstance(repos, list):
            return []

        return list(filter(lambda r: not r.get("archived"), repos))

    def get(self, request, *args, **kwargs):
        data = request.GET.dict()
        page = data.get("page", 1)
        org = data.get("org", settings.GITHUB_ORGS[0])

        repos = self.query(org, int(page))
        repo_serial = self.serializer_class(data=repos, many=True)
        repo_serial.is_valid(raise_exception=True)
        return Response(repo_serial.data)
