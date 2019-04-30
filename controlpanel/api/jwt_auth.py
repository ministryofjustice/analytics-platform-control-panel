from django.conf import settings
from jose import jwt
import requests
from requests.exceptions import RequestException
from rest_framework import HTTP_HEADER_ENCODING, authentication, exceptions

from controlpanel.api.models import User


class JWTAuthentication(authentication.BaseAuthentication):

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        try:
            unverified_header = jwt.get_unverified_header(raw_token)
        except jwt.JWTError as jwt_error:
            raise exceptions.AuthenticationFailed(jwt_error)

        try:
            key = self.get_matching_jwk(unverified_header['kid'])
        except KeyError as key_error:
            raise exceptions.AuthenticationFailed(key_error)
        except RequestException as req_error:
            raise exceptions.AuthenticationFailed(req_error)

        try:
            payload = jwt.decode(
                raw_token,
                key=key,
                algorithms=[settings.OIDC_RP_SIGN_ALGO],
                audience=settings.OIDC_RP_CLIENT_ID,
                options={
                    "verify_signature": False,
                    "verify_aud": False,
                },
            )
        except jwt.JWTError as jwt_error:
            raise exceptions.AuthenticationFailed(jwt_error)

        return self.get_user(payload), None

    def get_header(self, request):
        header = request.META.get('HTTP_AUTHORIZATION')

        if isinstance(header, bytes):
            # workaround test client
            header = header.decode(HTTP_HEADER_ENCODING)

        return header

    def get_raw_token(self, header):
        parts = header.split()

        if len(parts) == 0:
            return None

        # keep supporting old custom "JWT" header
        if parts[0] not in ('Bearer', 'JWT'):
            return None

        if len(parts) != 2:
            raise exceptions.AuthenticationFailed(
                "Authorization header must contain two space-delimited values",
            )

        return parts[1]

    def get_matching_jwk(self, key_id):
        response_jwks = requests.get(
            settings.OIDC_OP_JWKS_ENDPOINT,
            verify=False,
        )
        response_jwks.raise_for_status()
        jwks = response_jwks.json()

        for jwk in jwks.get('keys', []):
            if jwk['kid'] == key_id:
                return jwk

        raise KeyError('No matching JWK found')

    def get_user(self, payload):
        user, created = User.objects.get_or_create(
            pk=payload["sub"],
            username=payload[settings.OIDC_FIELD_USERNAME],
            email=payload[settings.OIDC_FIELD_EMAIL],
            name=payload[settings.OIDC_FIELD_NAME],
        )
        if created:
            user.aws_create_role()
            user.helm_create()

        return user
