import json
from github import Github, GithubException, UnknownObjectException
from django.conf import settings
import structlog

log = structlog.getLogger(__name__)
import requests



class GithubAPI:
    def __init__(self, api_token):
        """
        The api_token is the
        """
        self.api_token = api_token
        self.github = Github(api_token)
        self.header = dict(Authorization=f'token {api_token}', Accept='application/vnd.github+json')

    def get_repos(self, org: str, page: int):
        params = dict(page=page, per_page=100, sort='created', direction='desc')
        result = requests.get(f'{settings.GITHUB_BASE_URL}/orgs/{org}/repos', params, headers=self.header)
        if result.status_code == 200:
            return result.json()
        return []

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
                f"Failed getting {repo_name} Github repo for current login user: {err}"
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
