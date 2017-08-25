import jwt
from django.conf import settings
from jwt.exceptions import InvalidTokenError
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from control_panel_api.models import User


class Auth0JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        try:
            prefix, token = get_authorization_header(request).split()
        except (ValueError, TypeError):
            return None

        if prefix != settings.AUTH0_JWT_PREFIX.encode():
            raise AuthenticationFailed('JWT prefix missing')

        try:
            decoded = jwt.decode(token, key=settings.AUTH0_SECRET, audience=settings.AUTH0_AUDIENCE)
        except InvalidTokenError:
            raise AuthenticationFailed('JWT decode error')

        try:
            username = decoded.get(settings.AUTH0_USERNAME_FIELD)
        except KeyError:
            raise AuthenticationFailed('JWT missing {} username field'.format(settings.AUTH0_USERNAME_FIELD))

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed('No such user')

        return user, None
