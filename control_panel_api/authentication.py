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
            raise AuthenticationFailed('JWT prefix missing')

        try:
            decoded = jwt.decode(
                token,
                key=settings.AUTH0_CLIENT_SECRET,
                audience=settings.AUTH0_CLIENT_ID
            )

        except InvalidTokenError as error:
            raise AuthenticationFailed(error)

        sub = decoded.get('sub')

        if sub is None:
            raise AuthenticationFailed('JWT missing "sub" field')

        try:
            user = User.objects.get(auth0_id=sub)

        except User.DoesNotExist:
            raise AuthenticationFailed(f'No such user: {sub}')

        return user, None
