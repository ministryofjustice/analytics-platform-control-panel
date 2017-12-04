from django.conf import settings
import jwt
from jwt.exceptions import InvalidTokenError
from rest_framework.authentication import (
    BaseAuthentication,
    get_authorization_header
)
from rest_framework.exceptions import AuthenticationFailed

from control_panel_api.models import User


class Auth0JWTAuthentication(BaseAuthentication):

    def authenticate(self, request):

        try:
            prefix, token = get_authorization_header(request).split()

        except (ValueError, TypeError):
            return None

        if prefix != 'JWT'.encode():
            return None

        try:
            decoded = jwt.decode(
                token,
                key=settings.OIDC_CLIENT_SECRET,
                audience=settings.OIDC_CLIENT_ID
            )

        except InvalidTokenError as error:
            raise AuthenticationFailed(error)

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
