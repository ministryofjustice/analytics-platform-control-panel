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
        return user
    except User.DoesNotExist:
        pass
    logger.info('User "{}" is new. Will add it to the db, create aws role and '
                'create its charts on k8s.'.format(decoded_payload.get('sub')))
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
    except Exception:
        # the steps above are essential to the user, so if they don't
        # complete, we want to runthem again on the user's next attempt
        # request, because there's a good chance the problem was temporary.
        # Examples of errors:
        # * "Max number of attempts exceeded (1) when attempting to retrieve
        #   data from metadata service."
        # * k8s apiserver is momentarily down
        # delete the user so that this method runs again on the next request
        user.delete()

        # TODO deal with the problem of a failed helm install causing:
        # "Error: a release named init-user-joebloggs already exists."
        #  Consider doing:
        # https://github.com/helm/helm/issues/3353#issuecomment-385222233

        raise

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
