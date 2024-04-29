# Third-party
from django.conf import settings
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

# First-party/Local
from controlpanel.api import permissions
from controlpanel.api.github import GithubAPI
from controlpanel.api.serializers import GithubItemSerializer


class RepoApi(GenericAPIView):
    serializer_class = GithubItemSerializer
    permission_classes = (permissions.AppPermissions,)
    action = "retrieve"

    def get_queryset(self):
        return []

    def query(self, org: str, page: int):
        token = self.request.user.github_api_token
        repos = GithubAPI(token, github_org=org).get_repos(page)

        if not isinstance(repos, list):
            return []

        return list(filter(lambda r: not r.get("archived"), repos))

    def get(self, request, *args, **kwargs):
        data = request.GET.dict()
        page = data.get("page", 1)
        org_name = kwargs.get("org_name", settings.GITHUB_ORGS[0])

        repos = self.query(org_name, int(page))
        repo_serial = self.serializer_class(data=repos, many=True)
        repo_serial.is_valid(raise_exception=True)
        return Response(repo_serial.data)


class RepoEnvironmentAPI(GenericAPIView):
    def get(self, request, *args, **kwargs):
        org_name = kwargs.get("org_name", settings.GITHUB_ORGS[0])
        repo_name = kwargs["repo_name"]

        repo_envs = GithubAPI(request.user.github_api_token, github_org=org_name).get_repo_envs(
            repo_name
        )
        return Response(repo_envs)
