import logging

from django.conf import settings
from jose import jwt
from jose.exceptions import JWTError
import requests
from requests.exceptions import RequestException
from rest_framework.authentication import (
    BaseAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed

from control_panel_api.models import User

logger = logging.getLogger(__name__)


def get_jwks():
    response = requests.get(settings.OIDC_WELL_KNOWN_URL)
    return response.json()


def get_key(jwks, kid):
    for jwk in jwks.get('keys'):
        if jwk['kid'] == kid:
            return jwk

    return None


def get_jwk(kid):
    jwks = get_jwks()

    return get_key(jwks, kid)


class Auth0JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        try:
            prefix, token = get_authorization_header(request).split()
        except (ValueError, TypeError):
            return None

        if prefix != 'JWT'.encode():
            return None

        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as e:
            raise AuthenticationFailed('Error decoding JWT header') from e

        try:
            key = get_jwk(unverified_header['kid'])
        except RequestException as e:
            logger.error(e)
            raise AuthenticationFailed(e) from e

        if key is None:
            raise AuthenticationFailed('kid matching failure')

        try:
            decoded = jwt.decode(
                token,
                key=key,
                algorithms=['RS256'],
                audience=settings.OIDC_CLIENT_ID
            )
        except JWTError as e:
            logger.error(e)
            raise AuthenticationFailed(e) from e

        sub = decoded.get('sub')

        if sub is None:
            raise AuthenticationFailed('JWT missing "sub" field')

        try:
            user = User.objects.get(pk=sub)
        except User.DoesNotExist:
            user = User.objects.create(
                pk=sub,
                username=decoded.get(settings.OIDC_FIELD_USERNAME),
                email=decoded.get(settings.OIDC_FIELD_EMAIL),
                name=decoded.get(settings.OIDC_FIELD_NAME),
            )
            user.save()
            user.helm_create()

        return user, None
