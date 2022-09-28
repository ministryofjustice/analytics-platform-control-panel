from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from controlpanel.api import permissions
from controlpanel.api.github import GithubAPI

from controlpanel.api import permissions
from controlpanel.api.serializers import (
    ToolSerializer,
    GithubSerializer,
)
from controlpanel.api.models import (
    Tool,
    ToolDeployment,
)
from django.conf import settings
from django.core.cache import cache
import time

class ToolViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    filter_backends = []
    model = Tool
    pagination_class = None
    permission_classes = (permissions.ToolPermissions,)
    serializer_class = ToolSerializer


class RepoApi(GenericAPIView):
    serializer_class = GithubSerializer
    permission_classes = (permissions.IsSuperuser,)

    def get_queryset(self):
        return []

    def query(self, org: str, page: int):
        cache_key = f'{org}:repos:{page}'
        result = cache.get(cache_key)
        if result is not None and len(result):
            return result

        repos = GithubAPI(self.request.user.github_api_token).get_repos(org, page)
        result = [
            dict(html_url=repo.get('html_url'), full_name=repo.get('full_name')) for repo in repos if not repo.get('archived')
        ]

        timeout = page * 20
        if page > 3:
            # 3 hour cache
            timeout = 60 * 60 * 3
        cache.set(cache_key, result, timeout=timeout)
        return result

    def get(self, request, *args, **kwargs):
        data = request.GET.dict()
        page = data.get('page', 1)
        org = data.get('org', settings.GITHUB_ORGS[0])
        
        repos = self.query(org, int(page))

        serializers = self.get_serializer(data=repos, many=True)
        serializers.is_valid()
        return Response(serializers.data)