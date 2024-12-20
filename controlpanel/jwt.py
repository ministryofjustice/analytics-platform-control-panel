# Third-party
import jwt
import structlog
from django.conf import settings
from jwt.exceptions import DecodeError, InvalidTokenError, PyJWKClientError
from rest_framework import HTTP_HEADER_ENCODING

log = structlog.getLogger(__name__)


class JWT:
    def __init__(self, raw_token):
        self._header = None
        self._jwk = None
        self._payload = None
        self._raw_token = raw_token
        self.jwks_url = settings.OIDC_OP_JWKS_ENDPOINT
        self.decode_options = {
            "algorithms": [settings.OIDC_RP_SIGN_ALGO],
            "audience": settings.OIDC_CPANEL_API_AUDIENCE,
            "options": {
                "require": ["sub"],
            },
        }

    def __str__(self):
        return self._raw_token

    @property
    def header(self):
        if not self._header:
            try:
                self._header = jwt.get_unverified_header(self._raw_token)
            except (DecodeError, InvalidTokenError):
                return None
        return self._header

    @property
    def jwk(self):
        if not self._jwk and self.header:
            try:
                jwks_client = jwt.PyJWKClient(self.jwks_url)
                jwk = jwks_client.get_signing_key_from_jwt(self._raw_token)

                if jwk.key_id != self.header["kid"]:
                    raise DecodeError("Key ID mismatch")

                self._jwk = jwk.key

            except PyJWKClientError as error:
                raise DecodeError(f"Failed fetching JWK: {error}")

        return self._jwk

    @property
    def payload(self):
        if not self._payload:
            try:
                self._payload = jwt.decode(
                    self._raw_token,
                    key=self.jwk,
                    **self.decode_options,
                )
            except (DecodeError, KeyError) as error:
                raise DecodeError(f"Failed decoding JWT: {error}")
        return self._payload

    def validate(self):
        try:
            self._payload = jwt.decode(
                self._raw_token,
                key=self.jwk,
                **self.decode_options,
            )
        except (DecodeError, KeyError) as error:
            raise DecodeError(f"Failed decoding JWT: {error}")

    @classmethod
    def from_auth_header(cls, request):
        """
        Parse the HTTP_AUTHORIZATION header from the given request and extract the
        JWT if present
        """
        header = request.META.get("HTTP_AUTHORIZATION")

        if header is None:
            return None

        # workaround for Django test client
        if isinstance(header, bytes):
            header = header.decode(HTTP_HEADER_ENCODING)

        type, _, credential = header.partition(" ")

        # accept legacy non-standard 'JWT' prefix
        if type.lower() not in ("jwt", "bearer"):
            return None

        return cls(credential)
