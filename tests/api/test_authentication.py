# Standard library
from unittest.mock import patch

# Third-party
import pytest
from jose import JWTError, jwk, jwt
from requests.exceptions import Timeout

# First-party/Local
from controlpanel.api.models import User

TEST_CLIENT_ID = "test-client-id"
TEST_KID = "test-key-id"
TEST_SUB = "github|1234"

# The RSA key below is for testing only. DO NOT USE for anything else.
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQCo/FYLtMEuzwVf5n0ml+znmXF3hgj/i4W0ZndaL7GL1C+JpdQQ
yXGVKom2TyDMRPAwcL7D2shGO+dxAJQ0D2475Grk+rwBSBmtxea/glL7Fi6eMCKj
B7vwFf0jw8mDhjfKBtBKOdfEaEs7+0D32XCkYnq9IFoHfA1uQMhlVFdiBwIDAQAB
AoGABM0WjMKX8oKDPpRH3f7XBkV/ycuPGeOW6uc2YOOWAckHiLujaM6wYXKR8xIQ
dn1G7blmUh43LnepPbasf0Yo9ZLPKKbo/AMd8nS59Q0WHlIKUJ9DLnfxjpEzigZ4
PjEISBcmXbjg2Icq0b9xoeLC9X0aFEYbSGQJbA7L0snAOTECQQDgsKTxTxby1Ma4
SYdKwxhxchb4BD3NjvFAyx/FDmVHtbezOhng1va1TsM3aB95xIu8K8SNSSm/Hgi0
bDkVlVgLAkEAwIiN2EFXwioDjstyF8eC7leFoKKxykIZID+YerT6UoQd9Bu0trDe
Mh0RVsSW4D5Y/CjV5v5f5NT8eoDNKbiPdQJAV26lYHkkNu3xPfjuunrcYhjBM1WD
Lx/2ZP4lqKqHYrYle4qaU1GSws6ZTFAqH1oJ/fkSDOBxbDslq/+I3ws0LQJAIFAK
tkupJd4VQMbmPBVw5P1tYNtNSWu0edQSjC2JgYXI3So1NyAR+okkWtKdm777Aj78
P0tb3rTcNtcdF65w7QJBAIlfLWXrnjuJP4xdsJpubct+VoPZpEkojXp16zdEPSni
Tk1/Hf+kxTTBR5xfmgtLCPmOU8d+qodjxI6JmZtfvVU=
-----END RSA PRIVATE KEY-----"""  # gitleaks:allow

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCo/FYLtMEuzwVf5n0ml+znmXF3
hgj/i4W0ZndaL7GL1C+JpdQQyXGVKom2TyDMRPAwcL7D2shGO+dxAJQ0D2475Grk
+rwBSBmtxea/glL7Fi6eMCKjB7vwFf0jw8mDhjfKBtBKOdfEaEs7+0D32XCkYnq9
IFoHfA1uQMhlVFdiBwIDAQAB
-----END PUBLIC KEY-----"""


@pytest.fixture(autouse=True)
def audience(settings):
    # override django settings
    settings.OIDC_CPANEL_API_AUDIENCE = TEST_CLIENT_ID


@pytest.fixture(autouse=True)
def jwks():
    key = jwk.construct(TEST_PUBLIC_KEY, "RS256")
    jwk_dict = key.to_dict()
    jwk_dict["kid"] = TEST_KID
    with patch("controlpanel.jwt.requests") as requests:
        response = requests.get.return_value
        response.json.return_value = {"keys": [jwk_dict]}
        yield requests


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def api_request(client):
    def make_request(**headers):
        filtered = {}
        for header, value in headers.items():
            if value is not None:
                filtered[header] = value
        return client.get(
            "/api/cpanel/v1/apps",
            follow=True,
            **filtered,
        )

    return make_request


def token(claims={}, headers={}):
    header = {
        "kid": TEST_KID,
        **headers,
    }
    payload = {
        "nickname": "test",
        "name": "Test User",
        "email": "test@example.com",
        "sub": TEST_SUB,
        "aud": TEST_CLIENT_ID,
        **claims,
    }
    return jwt.encode(payload, TEST_PRIVATE_KEY, "RS256", header)


@pytest.mark.parametrize(
    "auth_header, status",
    [
        (None, 403),
        (f"Bearer {token()}", 403),
        (f'Bearer {token(claims={"scope": "list:app"})}', 403),
        (f'Bearer {token(claims={"scope": "list:app", "gty": "client-credentials"})}', 200),
        (f'JWT {token(claims={"scope": "list:app", "gty": "client-credentials"})}', 200),
        (f"FOO {token()}", 403),
        ("Bearer invalid_token", 403),
        (f'Bearer {token(headers={"kid": "no_match"})}', 403),
    ],
    ids=[
        "No token",
        "Valid token but no scope",
        "Valid token with list scope but no gty claim",
        "Valid token with list scope and gty claim",
        "Legacy auth header format",
        "Malformed auth header",
        "Invalid token",
        "No matching JWKs",
    ],
)
def test_token_auth(api_request, auth_header, status):
    assert api_request(HTTP_AUTHORIZATION=auth_header).status_code == status


def test_bad_request_for_jwks(api_request, jwks):
    jwks.get.side_effect = Timeout("test_bad_request_for_jwks")
    assert api_request(HTTP_AUTHORIZATION=f"Bearer {token()}").status_code == 403


def test_decode_jwt_error(api_request):
    with patch("controlpanel.jwt.jwt") as jwt:
        jwt.decode.side_effect = JWTError("test_decode_jwt_error")

        assert api_request(HTTP_AUTHORIZATION=f"Bearer {token()}").status_code == 403
