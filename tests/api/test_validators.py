# Third-party
import pytest
from django.core.exceptions import ValidationError

# First-party/Local
from controlpanel.api import validators


def test_validate_env_prefix():
    with pytest.raises(ValidationError):
        validators.validate_env_prefix("foo-bucketname")

    validators.validate_env_prefix("test-bucketname")


@pytest.mark.parametrize(
    "ip_ranges_text, ip_error",
    [
        ("not an ip address", r"not an ip address"),
        ("123, 456", r"123"),
        ("192.168.0.0/28 192.168.0.1", r"192.168.0.0/28 192.168.0.1"),
        ("192.168.0.0.0", r"192.168.0.0.0"),
    ],
)
def test_validate_ip_ranges_fail(ip_ranges_text, ip_error):
    with pytest.raises(ValidationError, match=ip_error):
        validators.validate_ip_ranges(ip_ranges_text)


@pytest.mark.parametrize(
    "ip_ranges_text",
    ["192.168.0.0/28", "192.168.0.0/28, 192.168.0.1", "192.168.0.0/28 , 192.168.0.1"],
)
def test_validate_ip_ranges_pass(ip_ranges_text):
    validators.validate_ip_ranges(ip_ranges_text)


@pytest.mark.parametrize(
    "auth0_conn_name",
    [
        ("auth0_conn_name"),
        ("auth0_conn_name*"),
        ("auth0-conn-name-"),
        ("auth0-conn_1212name"),
        ("-auth0-conn_1212name"),
    ],
)
def test_validate_auth0_conn_name_fail(auth0_conn_name):
    with pytest.raises(ValidationError, match=r"is invalid, check Auth0 connection name"):
        validators.validate_auth0_conn_name(auth0_conn_name)


@pytest.mark.parametrize(
    "auth0_conn_name",
    [("auth0-Acd12onn-name"), ("1auth0-conn-name2"), ("auth0-1connsdTRname")],
)
def test_validate_auth0_conn_name_pass(auth0_conn_name):
    validators.validate_auth0_conn_name(auth0_conn_name)


@pytest.mark.parametrize("auth0_client_id", [("auth0_client_id*"), ("auth0_client*&_id")])
def test_validate_auth0_conn_name_fail2(auth0_client_id):
    with pytest.raises(ValidationError, match=r"is invalid, check Auth0 client_id"):
        validators.validate_auth0_client_id(auth0_client_id)


@pytest.mark.parametrize(
    "auth0_client_id",
    [("autH0_1client_id1"), ("1auth0-client_id"), ("Auth0_cLient_iD")],
)
def test_validate_auth0_conn_name_pass2(auth0_client_id):
    validators.validate_auth0_client_id(auth0_client_id)


@pytest.mark.parametrize(
    "url, error",
    [
        ("https://gitlab.com/org/repo", "Must be a Github hosted repository"),
        (
            "https://github.com/moj-analytical-services/repo",
            "Unknown Github organization",
        ),
        (
            "https://github.com/ministryofjustice/repo/",
            "Repository URL should not include a trailing slash",
        ),
        (
            "https://github.com/ministryofjustice/repo/subdir",
            "Repository URL should not include subdirectories",
        ),
        (
            "https://github.com/ministryofjustice/",
            "Repository URL is missing the repository name",
        ),
        ("https://github.com/ministryofjustice/repo", None),
    ],
)
def test_validate_github_repository_url(url, error):
    if not error:
        assert validators.validate_github_repository_url(url) is None
    else:
        with pytest.raises(ValidationError) as exc:
            validators.validate_github_repository_url(url)
            assert exc.value.args[0] == error
