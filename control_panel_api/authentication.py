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


def get_jwt(request):
    try:
        prefix, token = get_authorization_header(request).split()
    except (ValueError, TypeError):
        return None

    if prefix != 'JWT'.encode():
        return None

    return token


def get_jwks():
    response = requests.get(settings.OIDC_WELL_KNOWN_URL)
    return response.json()


def get_matching_key(kid, jwks):
    for jwk in jwks.get('keys'):
        if jwk['kid'] == kid:
            return jwk

    raise KeyError('kid matching failure')


def get_key(token):
    unverified_header = jwt.get_unverified_header(token)

    jwks = get_jwks()

    return get_matching_key(unverified_header['kid'], jwks)


def get_or_create_user(decoded_payload):
    try:
        user = User.objects.get(pk=decoded_payload.get('sub'))
    except User.DoesNotExist:
        user = User.objects.create(
            pk=decoded_payload.get('sub'),
            username=decoded_payload.get(settings.OIDC_FIELD_USERNAME),
            email=decoded_payload.get(settings.OIDC_FIELD_EMAIL),
            name=decoded_payload.get(settings.OIDC_FIELD_NAME),
        )
        user.save()
        user.helm_create()

    return user


class Auth0JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = get_jwt(request)

        if token is None:
            return None

        try:
            key = get_key(token)
        except JWTError as e:
            raise AuthenticationFailed('Error decoding JWT header') from e
        except RequestException as e:
            logger.error(e)
            raise AuthenticationFailed(e) from e
        except KeyError as e:
            raise AuthenticationFailed(e) from e

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

        if decoded.get('sub') is None:
            raise AuthenticationFailed('JWT missing "sub" field')

        user = get_or_create_user(decoded)

        return user, None
