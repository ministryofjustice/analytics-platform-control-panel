# Standard library
import json
import base64

# from dataclasses import dataclass, fields
from typing import Dict, List

# Third-party
import requests
import structlog
from django.conf import settings

log = structlog.getLogger(__name__)


class GithubAPIException(Exception):
    pass


class GithubAPI:
    def __init__(self, api_token, github_org=None):
        """
        The api_token is the
        """
        self.api_token = api_token
        self.github_org = github_org or settings.GITHUB_ORGS[0]

        self.headers = {
            "Authorization": 'Bearer {}'.format(self.api_token),
            "Content-Type": 'application/vnd.github+json',
            "X-GitHub-Api-Version": settings.GITHUB_VERSION
        }

    def get_repos(self, page: int) -> List[dict]:
        params = dict(page=page, per_page=100, sort="created", direction="desc")
        response = requests.get(self._get_org_api_url(api_call="repos"), params, headers=self.headers)
        return self._process_response(response)

    def get_all_repositories(self):
        repos = []
        page_cnt = 1
        page_result = self.get_repos(page_cnt)
        while len(page_result) > 0:
            repos.extend(page_result)
            page_cnt += 1
            page_result = self.get_repos(page_cnt)
        return repos

    def get_repository(self, repo_name):
        response = requests.get(self._get_repo_api_url(repo_name=repo_name, api_call=None), headers=self.headers)
        return self._process_response(response)

    def decoded_content(self):
        """
        :type: bytes
        """
        assert self.encoding == "base64", "unsupported encoding: %s" % self.encoding
        return

    def read_app_deploy_info(self, repo_name, deploy_file="deploy.json"):
        response = requests.get(self._get_repo_api_url(repo_name=repo_name, api_call=f"contents/{deploy_file}"),
                                headers=self.headers)
        result_content = self._process_response(response)
        if result_content:
            content = base64.b64decode(bytearray(result_content.get("content", "{}"), "utf-8"))
            return json.loads(content)
        else:
            return {}

    def _process_response(self, response):
        if response.status_code != 200:
            response.raise_for_status()
        if not response.text:
            raise GithubAPIException(response.status_code)
        try:
            return response.json()
        except ValueError:
            return response.text

    def _get_org_api_url(self, api_call):
        return f"{settings.GITHUB_BASE_URL}/orgs/{self.github_org}/{api_call}"

    def _get_repo_api_url(self, repo_name, api_call):
        return f"{settings.GITHUB_BASE_URL}/repos/{self.github_org}/{repo_name}/{api_call}"

    def get_repo_secrets(self, repo_name):
        response = requests.get(self._get_repo_api_url(repo_name, api_call="actions/secrets"))
        return self._process_response(response)

    def create_or_update_repo_secret(self, repo_name, secret_name):
        response = requests.put(self._get_repo_api_url(repo_name, api_call=f"actions/secrets/{secret_name}"))
        return self._process_response(response)

    def delete_repo_secret(self, repo_name, secret_name):
        response = requests.delete(self._get_repo_api_url(repo_name, api_call=f"actions/secrets/{secret_name}"))
        return self._process_response(response)
