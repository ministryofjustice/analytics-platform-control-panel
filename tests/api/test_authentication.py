# Standard library
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Third-party
import jwt
import jwt.algorithms
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.exceptions import DecodeError, PyJWKClientError

# First-party/Local
from controlpanel.api.models import User

TEST_CLIENT_ID = "test-client-id"
TEST_KID = "test-key-id"
TEST_SUB = "github|1234"


@pytest.fixture()
def rsa_key_pair():
    # Generate private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Generate and serialize public key
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem.decode(), public_pem.decode()


@pytest.fixture(autouse=True)
def audience(settings):
    # override django settings
    settings.OIDC_CPANEL_API_AUDIENCE = TEST_CLIENT_ID


@pytest.fixture(autouse=True)
def jwks(rsa_key_pair):
    _, public_key = rsa_key_pair

    with patch("controlpanel.jwt.jwt.PyJWKClient") as client:
        client_value = MagicMock()
        client_value.get_signing_key_from_jwt.return_value = MagicMock(
            key=public_key, key_id=TEST_KID
        )
        client.return_value = client_value
        yield client


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


def token(private_key, claims={}, headers={}):
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
    return jwt.encode(payload, private_key, "RS256", header)


@pytest.mark.parametrize(
    "claim_kwargs, header_prefix, header_override, status",
    [
        ({}, "Bearer", {}, 403),
        ({}, "Bearer", {}, 403),
        ({"scope": "list:app"}, "Bearer", {}, 403),
        ({"scope": "list:app", "gty": "client-credentials"}, "Bearer", {}, 200),
        ({"scope": "list:app", "gty": "client-credentials"}, "JWT", {}, 200),
        ({}, "FOO", {}, 403),
        ({}, "Bearer invalid_token", None, 403),
        ({}, "Bearer", {"kid": "no_match"}, 403),
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
def test_token_auth(
    api_request, rsa_key_pair, claim_kwargs, header_prefix, header_override, status
):
    private_key, _ = rsa_key_pair
    if header_prefix == "Bearer invalid_token":
        auth_header = header_prefix
    else:
        tok = token(private_key, claims=claim_kwargs, headers=header_override or {})
        auth_header = f"{header_prefix} {tok}"

    assert api_request(HTTP_AUTHORIZATION=auth_header).status_code == status


def test_bad_request_for_jwks(api_request, jwks, rsa_key_pair):
    jwks.return_value.get_signing_key_from_jwt.side_effect = PyJWKClientError(
        "test_bad_request_for_jwks"
    )
    private_key, _ = rsa_key_pair
    tok = token(private_key)
    assert api_request(HTTP_AUTHORIZATION=f"Bearer {tok}").status_code == 403


def test_decode_jwt_error(api_request, rsa_key_pair):
    private_key, _ = rsa_key_pair
    with patch("controlpanel.jwt.jwt") as jwt:
        jwt.decode.side_effect = DecodeError("test_decode_jwt_error")
        tok = token(private_key)
        assert api_request(HTTP_AUTHORIZATION=f"Bearer {tok}").status_code == 403
