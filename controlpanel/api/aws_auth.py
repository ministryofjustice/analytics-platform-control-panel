# Standard library
import uuid

# Third-party
import boto3
import structlog
from botocore.credentials import RefreshableCredentials
from botocore.session import get_session
from django.conf import settings

log = structlog.getLogger(__name__)

# check for max session duration
# https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use.html#id_roles_use_view-role-max-session
TTL = 1500  # default


class BotoSessionException(Exception):
    pass


class BotoSession:
    """
    Boto Helper class which lets us create refreshable session, so that we can
    cache the client or resource.
    """

    def __init__(
        self,
        region_name: str = None,
        profile_name: str = None,
        assume_role_name: str = None,
    ):
        self.assume_role_name = assume_role_name

        self.session_name = "{}_session".format(uuid.uuid4().hex)
        self.region_name = region_name or settings.AWS_DEFAULT_REGION
        self.profile_name = profile_name

    def _get_credential_by_default(self):
        log.info("Creating default session")
        boto3_ini_session = boto3.Session(
            region_name=self.region_name, profile_name=self.profile_name
        )
        session_credentials = boto3_ini_session.get_credentials()
        return session_credentials

    def _get_session_credentials_by_sts(self):
        """
        Get session credentials
        """
        log.warn("(for monitoring purpose) Refreshing AWS token....")
        boto3_ini_session = boto3.Session(region_name=self.region_name)
        sts_client = boto3_ini_session.client("sts", region_name=self.region_name)
        log.warn(f"Attempting to assume role: {self.assume_role_name}")
        response = sts_client.assume_role(
            RoleArn=self.assume_role_name,
            RoleSessionName=self.session_name,
            DurationSeconds=TTL,
        ).get("Credentials")
        log.warn(f"STS response: {response}")
        identity = sts_client.get_caller_identity()

        log.warn(f"sts_client caller identity: {identity}")

        return {
            "access_key": response.get("AccessKeyId"),
            "secret_key": response.get("SecretAccessKey"),
            "token": response.get("SessionToken"),
            "expiry_time": response.get("Expiration").isoformat(),
        }

    def refreshable_session(self) -> boto3.Session:
        """
        Get refreshable boto3 session.
        """
        try:
            if self.assume_role_name:
                log.warn(f"Refresh credentials with assume role ({self.assume_role_name})")
                refreshable_credentials = RefreshableCredentials.create_from_metadata(
                    metadata=self._get_session_credentials_by_sts(),
                    refresh_using=self._get_session_credentials_by_sts,
                    method="sts-assume-role",
                )
            else:
                log.warn("Refresh credentials by default, as no assume role provided")
                refreshable_credentials = self._get_credential_by_default()

            log.warn(f"Refreshable credentials created successfully: {refreshable_credentials}")
            # attach refreshable credentials current session
            session = get_session()
            session._credentials = refreshable_credentials
            session.set_config_variable("region", self.region_name)
            auto_refresh_session = boto3.Session(botocore_session=session)

            return auto_refresh_session
        except Exception as ex:
            log.error(
                "Failed to establish the refreshable token due to reason ({})".format(str(ex))
            )
            return boto3.Session()


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class AWSCredentialSessionSet(metaclass=SingletonMeta):
    def __init__(self):
        self.credential_sessions = {}

    def get_session(
        self, profile_name: str = None, assume_role_name: str = None, region_name: str = None
    ):
        credential_session_key = "{}_{}_{}".format(profile_name, assume_role_name, region_name)
        log.warn(f"Looking for {credential_session_key} in credential_sessions")
        log.warn(f"Existing credential_sessions: {self.credential_sessions}")
        if credential_session_key not in self.credential_sessions:
            log.warn(
                "(for monitoring purpose) Initialising the session ({})".format(
                    credential_session_key
                )
            )
            self.credential_sessions[credential_session_key] = BotoSession(
                region_name=region_name,
                profile_name=profile_name,
                assume_role_name=assume_role_name,
            ).refreshable_session()
        log.warn(f"Session found: {self.credential_sessions[credential_session_key]}")
        return self.credential_sessions[credential_session_key]
