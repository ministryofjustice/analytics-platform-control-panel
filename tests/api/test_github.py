from unittest.mock import Mock, patch

import pytest

from controlpanel.api.github import GithubAPI, RepositoryNotFound


@pytest.fixture()
def requests():
    """
    Mock calls to requests
    """
    with patch("controlpanel.api.github.requests") as requests:
        yield requests


@pytest.fixture()
def request_get_success(requests):
    """
    Mock calls to requests
    """
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"repo": "test-repo-name"}
    requests.get.return_value = response

    yield requests


@pytest.fixture()
def request_get_not_found(requests):
    """
    Mock calls to requests
    """
    response = Mock()
    response.status_code = 404
    requests.get.return_value = response

    yield requests


def test_get_repository_success(request_get_success):

    test_api_token = "abc123"
    response = GithubAPI(test_api_token).get_repository("test-repo-name")

    assert response["repo"] == "test-repo-name"


def test_get_repository_not_found(request_get_not_found):

    with pytest.raises(
        RepositoryNotFound, match="Repository 'test-repo-name' not found, it may be private"
    ):
        test_api_token = "abc123"
        GithubAPI(test_api_token).get_repository("test-repo-name")


def test_get_repository_contents_success(request_get_success):

    test_api_token = "abc123"
    response = GithubAPI(test_api_token).get_repository_contents(
        "test-repo-name", "some/resource/path"
    )

    assert response["repo"] == "test-repo-name"


def test_get_repository_contents_not_found(request_get_not_found):

    with pytest.raises(
        RepositoryNotFound,
        match="Repository path 'some/resource/path' in test-repo-name not found. It may not exist",
    ):
        test_api_token = "abc123"
        GithubAPI(test_api_token).get_repository_contents("test-repo-name", "some/resource/path")
