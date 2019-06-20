from django.conf import settings
from rest_framework import authentication, exceptions

from controlpanel.api.models import User
from controlpanel.jwt import JWT, JWTDecodeError


class JWTAuthentication(authentication.BaseAuthentication):
    """
    Authenticate requests to the REST API with a JWT bearer token
    """

    def authenticate(self, request):
        jwt = JWT.from_auth_header(request)

        if not jwt:
            # continue to next authentication method
            return None

        return get_or_create_user(jwt), None


def get_or_create_user(jwt):
    try:
        return User.objects.get(pk=jwt.payload['sub'])

    except User.DoesNotExist:
        return User.objects.create(
            pk=jwt.payload['sub'],
            username=jwt.payload[settings.OIDC_FIELD_USERNAME],
            email=jwt.payload[settings.OIDC_FIELD_EMAIL],
            name=jwt.payload[settings.OIDC_FIELD_NAME],
        )

    except JWTDecodeError as jwt_error:
        raise exceptions.AuthenticationFailed(jwt_error)
