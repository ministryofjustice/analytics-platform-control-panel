import structlog

from django.conf import settings
from jose import jwt
from jose.exceptions import JWTError
import requests
from requests.exceptions import RequestException
from rest_framework import HTTP_HEADER_ENCODING


log = structlog.getLogger(__name__)


class JWTDecodeError(Exception):
    pass


class JWT:

    def __init__(self, raw_token):
        self._header = None
        self._jwk = None
        self._payload = None
        self._raw_token = raw_token
        self.jwks_url = settings.OIDC_OP_JWKS_ENDPOINT
        self.decode_options = {
            'algorithms': [settings.OIDC_RP_SIGN_ALGO],
            'audience': settings.OIDC_CPANEL_API_AUDIENCE,
            'options': {
                'require_sub': True,
            },
        }

    def __str__(self):
        return self._raw_token

    @property
    def header(self):
        if not self._header:
            try:
                self._header = jwt.get_unverified_header(self._raw_token)
            except jwt.JWTError:
                return None
        return self._header

    @property
    def jwk(self):
        if not self._jwk and self.header:
            try:
                response = requests.get(self.jwks_url, verify=False)
                response.raise_for_status()
            except RequestException as error:
                raise JWTDecodeError(f'Failed fetching JWK: {error}')

            jwks = response.json()

            for jwk in jwks.get('keys', []):
                if jwk['kid'] == self.header['kid']:
                    self._jwk = jwk
                    return self._jwk

            raise JWTDecodeError(
                f'No JWK with id {self.header["kid"]} found at {self.jwks_url} '
                f'while decoding {self._raw_token}'
            )

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
            except (JWTError, KeyError) as error:
                raise JWTDecodeError(f'Failed decoding JWT: {error}')
        return self._payload

    def validate(self):
        try:
            self._payload = jwt.decode(
                self._raw_token,
                key=self.jwk,
                **self.decode_options,
            )
        except (JWTError, KeyError) as error:
            raise JWTDecodeError(f'Failed decoding JWT: {error}')

    @classmethod
    def from_auth_header(cls, request):
        """
        Parse the HTTP_AUTHORIZATION header from the given request and extract the
        JWT if present
        """
        header = request.META.get('HTTP_AUTHORIZATION')

        if header is None:
            return None

        # workaround for Django test client
        if isinstance(header, bytes):
            header = header.decode(HTTP_HEADER_ENCODING)

        type, _, credential = header.partition(' ')

        # accept legacy non-standard 'JWT' prefix
        if type.lower() not in ('jwt', 'bearer'):
            return None

        return cls(credential)
