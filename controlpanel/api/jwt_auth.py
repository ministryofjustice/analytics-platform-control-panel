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
        # creating a user via API authentication is risky
        # return User.objects.create(
        #     pk=jwt.payload['sub'],
        #     username=jwt.payload[settings.OIDC_FIELD_USERNAME],
        #     email=jwt.payload[settings.OIDC_FIELD_EMAIL],
        #     name=jwt.payload[settings.OIDC_FIELD_NAME],
        # )
        raise exceptions.AuthenticationFailed('Not authorised to access apis')
    except JWTDecodeError as jwt_error:
        raise exceptions.AuthenticationFailed(jwt_error)


from functools import wraps
import jwt

from django.http import JsonResponse

def get_token_auth_header(request):
    """Obtains the Access Token from the Authorization Header
    """
    auth = request.META.get("HTTP_AUTHORIZATION", None)
    parts = auth.split()
    token = parts[1]

    return token

def requires_scope(required_scope):
    """Determines if the required scope is present in the Access Token
    Args:
        required_scope (str): The scope required to access the resource
    """
    def require_scope(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = get_token_auth_header(args[0])
            decoded = jwt.decode(token, verify=False)
            if decoded.get("scope"):
                token_scopes = decoded["scope"].split()
                for token_scope in token_scopes:
                    if token_scope == required_scope:
                        return f(*args, **kwargs)
            response = JsonResponse({'message': 'You don\'t have access to this resource'})
            response.status_code = 403
            return response
        return decorated
    return require_scope
