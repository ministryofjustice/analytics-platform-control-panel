import jwt
from django.conf import settings
from jwt.exceptions import InvalidTokenError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from control_panel_api.models import User


class Auth0JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        try:
            prefix, token = request.META.get('HTTP_AUTHORIZATION', '').split()
        except (ValueError, TypeError):
            return None

        if prefix != 'JWT':
            raise AuthenticationFailed('JWT prefix missing')

        try:
            decoded = jwt.decode(token, key=settings.AUTH0_SECRET, audience=settings.AUTH0_AUDIENCE)
        except InvalidTokenError:
            raise AuthenticationFailed('JWT decode error')

        try:
            username = decoded['sub']
        except KeyError:
            raise AuthenticationFailed('JWT missing sub username field')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed('No such user')

        return (user, None)
