import logging

from django.conf import settings
from django.core.cache import cache
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
    jwks = cache.get(settings.OIDC_WELL_KNOWN_URL)

    if not jwks:
        response = requests.get(settings.OIDC_WELL_KNOWN_URL)
        jwks = response.json()
        cache.set(settings.OIDC_WELL_KNOWN_URL, jwks)

    return jwks


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
        logger.info('User "{}" is new. Will add it to k8s, create aws role and add to db.'
                    .format(decoded_payload.get('sub')))
        user = User.objects.create(
            pk=decoded_payload.get('sub'),
            username=decoded_payload.get(settings.OIDC_FIELD_USERNAME),
            email=decoded_payload.get(settings.OIDC_FIELD_EMAIL),
            name=decoded_payload.get(settings.OIDC_FIELD_NAME),
        )
        user.save()
        logger.info('User {} saved to db as: "{}"'
                    .format(decoded_payload.get('sub'), user))
        try:
            user.aws_create_role()
            user.helm_create()
        except:
            # these steps are essential, so if they don't complete, delete the user so that
            # they run again on the next later request. They are idempotent anyway.
            # e.g. "Max number of attempts exceeded (1) when attempting to retrieve data from metadata service."
            # or if apiserver is momentarily down
            user.delete()

    return user


class Auth0JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        logger.info(f'request arrived {request}')
        token = get_jwt(request)
        logger.info(f'token "{token}"')

        if token is None:
            return None

        try:
            key = get_key(token)
            logger.info(f'key "{key}"')
        except JWTError as e:
            logger.error(e)
            raise AuthenticationFailed('Error decoding JWT header') from e
        except RequestException as e:
            logger.error(e)
            raise AuthenticationFailed(e) from e
        except KeyError as e:
            logger.exception(e)
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
            logger.error(f'no "sub" field in jwt token')
            raise AuthenticationFailed('JWT missing "sub" field')

        logger.info('Received request with jwt token for subject {}'
                    .format(decoded['sub']))
        user = get_or_create_user(decoded)
        logger.info(f'user "{user}"')

        return user, None
