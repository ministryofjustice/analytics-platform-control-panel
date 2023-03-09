# Standard library
import base64
import json
from base64 import b64encode

# from dataclasses import dataclass, fields
from typing import List

# Third-party
import requests
import structlog
from django.conf import settings
from nacl import encoding, public

log = structlog.getLogger(__name__)


class GithubAPIException(Exception):
    pass


def extract_repo_info_from_url(repo_url):
    url_parts = repo_url.split("/")
    if len(url_parts) < 4:
        raise GithubAPIException("Wrong repo url")
    return url_parts[3], url_parts[4]


class GithubAPI:
    def __init__(self, api_token: str, github_org=None):
        """
        The api_token is the
        """
        self.api_token = api_token
        self.github_org = github_org or settings.GITHUB_ORGS[0]

        self.headers = {
            "Authorization": "Bearer {}".format(self.api_token),
            "Content-Type": "application/vnd.github+json",
            "X-GitHub-Api-Version": settings.GITHUB_VERSION,
        }

    def get_repos(self, page: int) -> List[dict]:
        params = dict(page=page, per_page=100, sort="created", direction="desc")
        response = requests.get(
            self._get_org_api_url(api_call="repos"), params, headers=self.headers
        )
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

    def get_repository(self, repo_name: str):
        response = requests.get(
            self._get_repo_api_url(repo_name=repo_name, api_call=None),
            headers=self.headers,
        )
        return self._process_response(response)

    def read_app_deploy_info(self, repo_name: str, deploy_file="deploy.json"):
        response = requests.get(
            self._get_repo_api_url(
                repo_name=repo_name, api_call=f"contents/{deploy_file}"
            ),
            headers=self.headers,
        )
        result_content = self._process_response(response)
        if result_content:
            content = base64.b64decode(
                bytearray(result_content.get("content", "{}"), "utf-8")
            )
            return json.loads(content)
        else:
            return {}

    def _process_response(self, response):
        if response.status_code >= 300:
            response.raise_for_status()
        if not response.text and response.status_code != 204:
            raise GithubAPIException(response.status_code)
        try:
            return response.json()
        except ValueError:
            return response.text

    def _get_org_api_url(self, api_call: str) -> str:
        return f"{settings.GITHUB_BASE_URL}/orgs/{self.github_org}/{api_call}"

    def _get_repo_api_url(self, repo_name: str, api_call: str) -> str:
        if api_call:
            return (
                f"{settings.GITHUB_BASE_URL}/repos/{self.github_org}/"
                f"{repo_name}/{api_call}"
            )
        else:
            return f"{settings.GITHUB_BASE_URL}/repos/{self.github_org}/{repo_name}"

    def _get_repo_env_api_url(
        self, repo_name: str, env_name: str, api_call: str, repo_id=None
    ) -> str:
        if not repo_id:
            repo_info = self.get_repository(repo_name)
            repo_id = repo_info.get("id", "")
        return (
            f"{settings.GITHUB_BASE_URL}/repositories/{repo_id}/"
            f"environments/{env_name}/{api_call}"
        )

    def _encrypt_secret(self, public_key: str, secret_value: str) -> str:
        """Encrypt a Unicode string using the public key."""
        public_key = public.PublicKey(
            public_key.encode("utf-8"), encoding.Base64Encoder()
        )
        sealed_box = public.SealedBox(public_key)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return b64encode(encrypted).decode("utf-8")

    def get_repo_envs(self, repo_name: str) -> list:
        response = requests.get(
            self._get_repo_api_url(repo_name, api_call="environments"),
            headers=self.headers,
        )
        return [
            item["name"]
            for item in self._process_response(response).get("environments", [])
        ]

    def get_repo_all_env_secrets(self, repo_name: str):
        secrets = []
        for env_name in self.get_repo_envs(repo_name):
            for item in self.get_repo_env_secrets(repo_name, env_name=env_name):
                item["env_name"] = env_name
                secrets.append(item)
        return secrets

    def get_repo_env_secrets(self, repo_name: str, env_name: str):
        response = requests.get(
            self._get_repo_env_api_url(repo_name, env_name, api_call="secrets"),
            headers=self.headers,
        )
        return self._process_response(response).get("secrets", [])

    def get_repo_env_public_key(self, repo_name: str, env_name: str):
        response = requests.get(
            self._get_repo_env_api_url(
                repo_name, env_name, api_call="secrets/public-key"
            ),
            headers=self.headers,
        )
        return self._process_response(response)

    def create_or_update_repo_env_secret(
        self,
        repo_name: str,
        env_name: str,
        secret_name: str,
        secret_value: str,
        repo_id=None,
        public_key=None,
    ):
        if not public_key:
            public_key = self.get_repo_env_public_key(repo_name, env_name)
        secret_data = {
            "encrypted_value": self._encrypt_secret(public_key["key"], secret_value),
            "key_id": public_key["key_id"],
        }
        repo_secret_url = self._get_repo_env_api_url(
            repo_name, env_name, api_call=f"secrets/{secret_name}", repo_id=repo_id
        )
        response = requests.put(
            repo_secret_url, data=json.dumps(secret_data), headers=self.headers
        )
        return self._process_response(response)

    def create_or_update_repo_env_secrets(
        self, repo_name: str, env_name: str, secret_data: dict
    ):
        repo_info = self.get_repository(repo_name)
        repo_id = repo_info.get("id", "")
        public_key = self.get_repo_env_public_key(repo_name, env_name)
        for secret_key, secret_value in secret_data.items():
            self.create_or_update_repo_env_secret(
                repo_name,
                env_name,
                secret_key,
                secret_value,
                repo_id=repo_id,
                public_key=public_key,
            )

    def delete_repo_env_secret(self, repo_name, env_name, secret_name):
        response = requests.delete(
            self._get_repo_env_api_url(
                repo_name, env_name, api_call=f"secrets/{secret_name}"
            ),
            headers=self.headers,
        )
        return self._process_response(response)

    def get_repo_all_env_vars(self, repo_name: str):
        env_vars = []
        for env_name in self.get_repo_envs(repo_name):
            for item in self.get_repo_env_vars(repo_name, env_name=env_name):
                item["env_name"] = env_name
                env_vars.append(item)
        return env_vars

    def get_repo_env_var(self, repo_name: str, env_name: str, var_name: str):
        response = requests.get(
            self._get_repo_env_api_url(
                repo_name, env_name, api_call=f"variables/{var_name}"
            ),
            headers=self.headers,
        )
        return self._process_response(response)

    def get_repo_env_vars(self, repo_name: str, env_name: str):
        response = requests.get(
            self._get_repo_env_api_url(repo_name, env_name, api_call="variables"),
            headers=self.headers,
        )
        return self._process_response(response).get("variables", [])

    def create_repo_env_var(
        self, repo_name: str, env_name: str, key_name: str, key_value: str, repo_id=None
    ):
        data = {"name": key_name, "value": str(key_value)}
        repo_var_url = self._get_repo_env_api_url(
            repo_name, env_name, api_call="variables", repo_id=repo_id
        )
        response = requests.post(
            repo_var_url, data=json.dumps(data), headers=self.headers
        )
        return self._process_response(response)

    def update_repo_env_var(
        self, repo_name: str, env_name: str, key_name: str, key_value: str, repo_id=None
    ):
        data = {"name": key_name, "value": str(key_value)}
        repo_var_url = self._get_repo_env_api_url(
            repo_name, env_name, api_call=f"variables/{key_name}", repo_id=repo_id
        )
        response = requests.patch(
            repo_var_url, data=json.dumps(data), headers=self.headers
        )
        return self._process_response(response)

    def delete_repo_env_var(
        self, repo_name: str, env_name: str, key_name: str, repo_id=None
    ):
        repo_var_url = self._get_repo_env_api_url(
            repo_name, env_name, api_call=f"variables/{key_name}", repo_id=repo_id
        )
        response = requests.delete(repo_var_url, headers=self.headers)
        return self._process_response(response)

    def create_repo_env_vars(self, repo_name: str, env_name: str, env_data: dict):
        repo_info = self.get_repository(repo_name)
        repo_id = repo_info.get("id", "")
        for env_key, env_value in env_data.items():
            try:
                self.create_repo_env_var(
                    repo_name, env_name, env_key, env_value, repo_id=repo_id
                )
            except Exception as error:
                log.warn("Error from creating variable: {}".format(str(error)))
                self.update_repo_env_var(
                    repo_name, env_name, env_key, env_value, repo_id=repo_id
                )

    def create_or_update_env_var(
        self, repo_name: str, env_name: str, key_name: str, key_value: str
    ):
        repo_info = self.get_repository(repo_name)
        repo_id = repo_info.get("id", "")
        try:
            self.create_repo_env_var(
                repo_name, env_name, key_name, key_value, repo_id=repo_id
            )
        except Exception as error:
            log.warn("Error from creating variable: {}".format(str(error)))
            self.update_repo_env_var(
                repo_name, env_name, key_name, key_value, repo_id=repo_id
            )
