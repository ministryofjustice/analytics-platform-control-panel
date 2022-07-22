import json
from github import Github, GithubException, UnknownObjectException
from django.conf import settings
import structlog


log = structlog.getLogger(__name__)


class GithubAPI:

    def __init__(self, api_token):
        """
        The api_token is the
        """
        self.api_token = api_token
        self.github = Github(api_token)

    def get_all_repositories(self):
        repos = []
        for name in settings.GITHUB_ORGS:
            try:
                org = self.github.get_organization(name)
                repos.extend(org.get_repos())
            except GithubException as err:
                log.warning(
                    f"Failed getting {name} Github org repos for current login user: {err}"
                )
                raise err
        return repos

    def get_repository(self, repo_name):
        try:
            return self.github.get_repo(repo_name)
        except UnknownObjectException as err:
            log.warning(
                f"Failed getting {repo_name} Github repo for current logoin user: {err}"
            )
            return None

    def read_app_deploy_info(self, repo_instance, deploy_file='deploy.json'):
        if repo_instance:
            try:
                return json.loads(repo_instance.get_contents(deploy_file).decoded_content)
            except UnknownObjectException:
                return {}
        else:
            raise("Please provide the valid repo instance")
