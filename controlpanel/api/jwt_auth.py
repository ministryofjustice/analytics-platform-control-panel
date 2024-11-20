# Standard library
from functools import wraps

# Third-party
from django.http import JsonResponse
from rest_framework import authentication, exceptions

# First-party/Local
from controlpanel.api.models import User
from controlpanel.jwt import JWT, JWTDecodeError

M2M_CLAIM_FLAG = "client-credentials"


class AuthenticatedServiceClient:
    """ "
    The client instance for authenticated M2M client. This class plays the role of "user" object but
    for M2M client as the django DRF auth model is based on User Model. This class instance is
    available through request.user.
    """

    def __init__(self, jwt_payload):
        self.jwt_payload = jwt_payload

    @property
    def is_authenticated(self):
        return True

    @property
    def is_admin(self):
        return False

    @property
    def pk(self):
        return self.jwt_payload["sub"]

    @property
    def scope(self):
        """
        each token scope follows format: <Operation>:<resource>
        """
        return self.jwt_payload.get("scope", "").split()

    @property
    def is_superuser(self):
        return False

    @property
    def is_client(self):
        return True

    def has_perm(self, perm, obj=None):
        return False


class JWTAuthentication(authentication.BaseAuthentication):
    """
    Authenticate requests to the REST API with a JWT bearer token
    As the REST API will be used by some clients which can provide the user identifier and
    M2M clients, the JWT token need to make sure both can be authenticated properly
    """

    def authenticate(self, request):
        jwt = JWT.from_auth_header(request)

        if not jwt:
            # continue to next authentication method
            return None
        else:
            try:
                jwt.validate()
            except JWTDecodeError:
                return None

        return self._get_client(jwt), None

    def _is_m2m(self, payload):
        return payload.get("gty", "") == M2M_CLAIM_FLAG

    def _get_client(self, jwt):
        """
        claim "sub" store the id of caller.
        """
        try:
            return User.objects.get(pk=jwt.payload["sub"])
        except User.DoesNotExist:
            # Return the service client model
            if self._is_m2m(jwt.payload):
                return AuthenticatedServiceClient(jwt.payload)
            else:
                raise exceptions.AuthenticationFailed()
        except JWTDecodeError:
            raise exceptions.AuthenticationFailed(
                "Failed to be authenticated due to JWT decoder error!"
            )

    @staticmethod
    def requires_scope(required_scope):
        """Determines if the required scope is present in the Access Token
        Args:
            required_scope (str): The scope required to access the resource
        """

        def require_scope(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                if len(args) >= 1:
                    # assume the request object is the second argument
                    client = args[1].user
                    for token_scope in client.scope:
                        if token_scope == required_scope:
                            return f(*args, **kwargs)
                response = JsonResponse({"message": "You don't have access to this resource"})
                response.status_code = 403
                return response

            return decorated

        return require_scope
