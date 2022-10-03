# Third-party
from django.conf import settings
from rest_framework import mixins, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

# First-party/Local
from controlpanel.api import permissions
from controlpanel.api.github import GithubAPI
from controlpanel.api.models import Tool
from controlpanel.api.serializers import GithubSerializer, ToolSerializer


class ToolViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    filter_backends = []
    model = Tool
    pagination_class = None
    permission_classes = (permissions.ToolPermissions,)
    serializer_class = ToolSerializer


class RepoApi(GenericAPIView):
    serializer_class = GithubSerializer
    permission_classes = (permissions.AppPermissions,)
    action = "retrieve"

    def get_queryset(self):
        return []

    def query(self, org: str, page: int):
        token = self.request.user.github_api_token
        repos = GithubAPI(token).get_repos(org, page)

        if not isinstance(repos, list):
            return []

        result = [
            {"html_url": r.get("html_url"), "full_name": r.get("full_name")}
            for r in repos
            if not r.get("archived") and "html_url" in r and "full_name" in r
        ]
        return result

    def get(self, request, *args, **kwargs):
        data = request.GET.dict()
        page = data.get("page", 1)
        org = data.get("org", settings.GITHUB_ORGS[0])

        repos = self.query(org, int(page))

        serializers = self.get_serializer(data=repos, many=True)
        serializers.is_valid()
        return Response(serializers.data)
