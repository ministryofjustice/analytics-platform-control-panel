# Standard library
import json
from dataclasses import dataclass, fields
from typing import Any, Dict, List

# Third-party
import requests
import structlog
from django.conf import settings
from github import Github, GithubException, UnknownObjectException

log = structlog.getLogger(__name__)


@dataclass
class BaseDataClass:
    @classmethod
    def from_dict(cls, dict_: dict) -> Any:
        class_fields = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in dict_.items() if k in class_fields})


@dataclass
class GithubRepo(BaseDataClass):
    html_url: str
    full_name: str
    archived: bool


class GithubAPI:
    def __init__(self, api_token):
        """
        The api_token is the
        """
        self.api_token = api_token
        self.github = Github(api_token)
        self.header = dict(
            Authorization=f"token {api_token}", Accept="application/vnd.github+json"
        )

    def get_repos(self, org: str, page: int) -> List[GithubRepo]:
        params = dict(page=page, per_page=100, sort="created", direction="desc")
        result = requests.get(
            f"{settings.GITHUB_BASE_URL}/orgs/{org}/repos", params, headers=self.header
        )

        try:
            if result.status_code == 200:
                data: List[Dict] = result.json()
                if not isinstance(data, list):
                    return []
                return [GithubRepo.from_dict(i) for i in data]

            result.raise_for_status()
        except requests.HTTPError as ex:
            log.error("github request failed {}".format(ex))
        except TypeError as t_ex:
            log.error("repo result missing keys {}".format(t_ex))
        return []

    def get_all_repositories(self):
        repos = []
        for name in settings.GITHUB_ORGS:
            try:
                org = self.github.get_organization(name)
                repos.extend(org.get_repos())
            except GithubException as err:
                log.warning(
                    f"Failed getting {name} Github org repos for current login user: {err}"  # noqa: E501
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

    def read_app_deploy_info(self, repo_instance, deploy_file="deploy.json"):
        if repo_instance:
            try:
                return json.loads(
                    repo_instance.get_contents(deploy_file).decoded_content
                )
            except UnknownObjectException:
                return {}
        else:
            raise ("Please provide the valid repo instance")
