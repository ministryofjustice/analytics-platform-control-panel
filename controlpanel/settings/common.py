# Standard library
import os
import sys
from os.path import abspath, dirname, join
from socket import gaierror, gethostbyname, gethostname

# Third-party
import structlog

# Name of the deployment environment (dev/alpha)
ENV = os.environ.get("ENV", "dev")

# -- Paths

# Name of the project
PROJECT_NAME = "controlpanel"

# Absolute path of project Django directory
DJANGO_ROOT = dirname(dirname(abspath(__file__)))

# Absolute path of project directory
PROJECT_ROOT = dirname(DJANGO_ROOT)

# Directory to collect static files into
STATIC_ROOT = join(PROJECT_ROOT, "run", "static")

# Directory for user uploaded files
MEDIA_ROOT = join(PROJECT_ROOT, "run", "media")

# Django looks in these locations for additional static assets to collect
STATICFILES_DIRS = [
    join(PROJECT_ROOT, "static"),
]


# -- Application

INSTALLED_APPS = [
    "daphne",
    # Django channels for asynchronous support
    "channels",
    # Django Admin
    "django.contrib.admin",
    # Django auth system
    "django.contrib.auth",
    # OIDC client
    "mozilla_django_oidc",
    # Django models
    "django.contrib.contenttypes",
    # Django sessions
    "django.contrib.sessions",
    # Django flash messages
    "django.contrib.messages",
    # Django postgres form and model
    "django.contrib.postgres",
    # Django collect static files into a single location
    "django.contrib.staticfiles",
    # Make current request available anywhere
    "crequest",
    # Provides shell_plus, runserver_plus, etc
    "django_extensions",
    # Provides filter backend for use with Django REST Framework
    "django_filters",
    # Provides redis cache
    "django_redis",
    # Django REST Framework
    "rest_framework",
    # Django Rules object permissions
    "rules",
    # Logs changes to models
    "simple_history",
    # Analytics Platform Control Panel API
    "controlpanel.api",
    # Analytics Platform Control Panel Kubernetes API proxy
    "controlpanel.kubeapi",
    # Analytics Platform Control Panel Frontend
    "controlpanel.frontend",
    # Analytics Platform Control Panel CLI tools"
    "controlpanel.cli",
    # Health check
    "django_prometheus",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "controlpanel.middleware.DisableClientSideCachingMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Make current request available anywhere
    "crequest.middleware.CrequestMiddleware",
    # Check user's OIDC token is still valid
    "mozilla_django_oidc.middleware.SessionRefresh",
    # Structured logging
    "django_structlog.middlewares.RequestMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
    # Track which user made changes to models utilising django-simple-history
    "simple_history.middleware.HistoryRequestMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [
            # find local component templates
            join(DJANGO_ROOT, "frontend", "static", "components"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "environment": f"{PROJECT_NAME}.frontend.jinja2.environment",
        },
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    },
]


# -- Auth

# List of classes used when attempting to authenticate a user
AUTHENTICATION_BACKENDS = [
    # Needed for OIDC auth
    "controlpanel.oidc.OIDCSubAuthenticationBackend",
    # Needed for Basic Auth
    "django.contrib.auth.backends.ModelBackend",
    # Needed for object permissions
    "rules.permissions.ObjectPermissionBackend",
]

# List of validators used to check the strength of users' passwords
AUTH_PASSWORD_VALIDATORS = []

# Custom user model class
AUTH_USER_MODEL = "api.User"

# URL where requests are redirected for login
# This is set to the mozilla-django-oidc login view name
LOGIN_URL = "oidc_authentication_init"

# URL where requests are redirected after logging out (if not specified)
LOGOUT_REDIRECT_URL = "/"

# URL where requests are redirected after a failed login
LOGIN_REDIRECT_URL_FAILURE = "/login-fail/"

# Length of time it takes for an OIDC ID token to expire (default 12 hours)
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 60 * 60 * 12  # 12 hours

# Gracefully handle state mismatch
OIDC_CALLBACK_CLASS = "controlpanel.oidc.StateMismatchHandler"

# Hostname of the OIDC provider
OIDC_DOMAIN = os.environ.get("OIDC_DOMAIN")

# Provider for cloud platform
OIDC_APP_EKS_PROVIDER = os.environ.get("OIDC_APP_EKS_PROVIDER")

# OIDC endpoints
OIDC_OP_AUTHORIZATION_ENDPOINT = os.environ.get("OIDC_OP_AUTHORIZATION_ENDPOINT")
OIDC_OP_JWKS_ENDPOINT = os.environ.get("OIDC_OP_JWKS_ENDPOINT")
OIDC_OP_TOKEN_ENDPOINT = os.environ.get("OIDC_OP_TOKEN_ENDPOINT")
OIDC_OP_USER_ENDPOINT = os.environ.get("OIDC_OP_USER_ENDPOINT")

# Function called to logout of OIDC provider
OIDC_OP_LOGOUT_URL_METHOD = "controlpanel.oidc.logout"

# OIDC client secret
OIDC_RP_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID")
OIDC_RP_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET")

# OIDC JWT signing algorithm
OIDC_RP_SIGN_ALGO = os.environ.get("OIDC_RP_SIGN_ALGO", "RS256")

# Commented out the offline_access for refresh_token for now as we haven't
# implemented the refresh_token flow yet.
# OIDC_RP_SCOPES = "openid email profile offline_access"
OIDC_RP_SCOPES = "openid email profile"


# OIDC claims
OIDC_FIELD_EMAIL = "email"
OIDC_FIELD_NAME = "name"
OIDC_FIELD_USERNAME = "nickname"
OIDC_STORE_ID_TOKEN = True

# Auth0
AUTH0 = {
    "client_id": OIDC_RP_CLIENT_ID,
    "client_secret": OIDC_RP_CLIENT_SECRET,
    "domain": OIDC_DOMAIN,
    "authorization_extension_url": os.environ.get("OIDC_AUTH_EXTENSION_URL"),
    "logout_url": f"https://{OIDC_DOMAIN}/v2/logout",
    "authorization_extension_audience": "urn:auth0-authz-api",
}

OIDC_DRF_AUTH_BACKEND = "controlpanel.oidc.OIDCSubAuthenticationBackend"

# The audience for Control Panel RESTful APIs
OIDC_CPANEL_API_AUDIENCE = os.environ.get("OIDC_CPANEL_API_AUDIENCE")

# For authentication with EntraID
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID")
AZURE_OP_CONF_URL = (
    f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/v2.0/.well-known/openid-configuration"
)
AZURE_RP_SCOPES = "openid email profile"
AZURE_CODE_CHALLENGE_METHOD = os.environ.get("AZURE_CODE_CHALLENGE_METHOD", "S256")
AUTHLIB_OAUTH_CLIENTS = {
    "azure": {
        "client_id": os.environ.get("AZURE_CLIENT_ID"),
        "client_secret": os.environ.get("AZURE_CLIENT_SECRET"),
        "server_metadata_url": AZURE_OP_CONF_URL,
        "client_kwargs": {
            "scope": AZURE_RP_SCOPES,
            "response_type": "code",
            "token_endpoint_auth_method": "client_secret_post",
            "code_challenge_method": AZURE_CODE_CHALLENGE_METHOD,
            "prompt": "login",
        },
    }
}

# -- Security

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")

# A list of people who get code error notifications when DEBUG=False
ADMINS = []

# A list of people who get broken link notifications when
# BrokenLinkEmailsMiddleware is enabled
MANAGERS = []

# Whitelist values for the HTTP Host header, to prevent certain attacks
ALLOWED_HOSTS = [host for host in os.environ.get("ALLOWED_HOSTS", "").split() if host] + [
    "cpanel.cpanel"
]


# set this before adding the IP address below
# TODO We may be able to set this in terraform instead, we should check this
QUICKSIGHT_DOMAINS = []
for host in ALLOWED_HOSTS:
    prefix = "*" if host.startswith(".") else ""
    QUICKSIGHT_DOMAINS.append(f"https://{prefix}{host}")

try:
    ALLOWED_HOSTS.append(gethostbyname(gethostname()))
except gaierror:
    pass

# Sets the X-XSS-Protection: 1; mode=block header
SECURE_BROWSER_XSS_FILTER = True

# Sets the X-Content-Type-Options: nosniff header
SECURE_CONTENT_TYPE_NOSNIFF = True

# Secure the CSRF cookie
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

# Secure the session cookie
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True


# -- Running Django

# Path to WSGI application
WSGI_APPLICATION = f"{PROJECT_NAME}.wsgi.application"

# Path to root URL configuration
ROOT_URLCONF = f"{PROJECT_NAME}.urls"

# URL path where static files are served
STATIC_URL = "/static/"

# URL path where uploaded files are served
MEDIA_URL = ""


# -- Debug

# Activates debugging
DEBUG = str(os.environ.get("DEBUG", False)).lower() == "true"

# -- Database
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
ENABLE_DB_SSL = (
    str(os.environ.get("ENABLE_DB_SSL", DB_HOST not in ["127.0.0.1", "localhost"])).lower()
    == "true"
)
DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", PROJECT_NAME),
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": DB_HOST,
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

if ENABLE_DB_SSL:
    DATABASES["default"]["OPTIONS"] = {"sslmode": "require"}

# Wrap each request in a transaction
ATOMIC_REQUESTS = True


# -- Internationalization

# Enable Django translation system
USE_I18N = False

# Enable localized formatting of numbers and dates
USE_L10N = False

# Language code - ignored unless USE_I18N is True
LANGUAGE_CODE = "en-gb"

# Make Django use timezone-aware datetimes internally
USE_TZ = True

# Time zone
TIME_ZONE = "UTC"


# -- Django REST Framework

# questions: the list of authentication methods, as long as one of them is met, it will be passed.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Token authentication
        # need to check why a user can be created automatically
        # during a process of authentication flow for our cases
        "controlpanel.api.jwt_auth.JWTAuthentication",
        # save question as above
        "mozilla_django_oidc.contrib.drf.OIDCAuthentication",
        # REMOVE basic auth from the authentication methods
        # 'rest_framework.authentication.BasicAuthentication',
        # Require browsable api and also allow frontend to call api via session
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": ["controlpanel.api.filters.SuperusersOnlyFilter"],
    "DEFAULT_PERMISSION_CLASSES": ["controlpanel.api.permissions.IsSuperuser"],
    "DEFAULT_PAGINATION_CLASS": "controlpanel.api.pagination.CustomPageNumberPagination",  # noqa: E501
    "PAGE_SIZE": 100,
}


# -- Sentry error tracking

if os.environ.get("SENTRY_DSN"):
    SENTRY_ENVIRONMENT = ENV
    KUBERNETES_ENV = "EKS"
    if ENV == "alpha":
        SENTRY_ENVIRONMENT = "prod"
    # Third-party
    import sentry_sdk
    from sentry_sdk import set_tag
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        environment=SENTRY_ENVIRONMENT,
        integrations=[DjangoIntegration(), RedisIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=True,
    )
    set_tag("Kubernetes Env", KUBERNETES_ENV)
    if "runworker" in sys.argv:
        set_tag("RunningIn", "Worker")
    elif "shell" in sys.argv:
        set_tag("RunningIn", "Shell")


# -- Static files

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]


# -- Redis
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
REDIS_PORT = "6379"
REDIS_SCHEME = os.environ.get("REDIS_SCHEME", "redis")
if REDIS_SCHEME not in ["redis", "rediss"]:
    raise ValueError(
        f"Invalid value for 'REDIS_SCHEME' environment variable. Must be 'redis' or 'rediss' (to use SSL/TLS). It was '{REDIS_SCHEME}' which is invalid."  # noqa: E501
    )

REDIS_URI = f"{REDIS_SCHEME}://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/1"

# -- Prometheus

PROMETHEUS_EXPORT_MIGRATIONS = False

# -- Async

ASGI_APPLICATION = f"{PROJECT_NAME}.routing.application"

# See: https://pypi.org/project/channels-redis/
# https://github.com/django/channels_redis/issues/332
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.pubsub.RedisPubSubChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "address": REDIS_URI,
                    "socket_timeout": 30,
                }
            ],
        },
    },
}

# -- Cache
if REDIS_HOST and REDIS_PORT and REDIS_PASSWORD:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URI,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "PASSWORD": f"{REDIS_PASSWORD}",
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "control-panel",
        }
    }


# -- Github
GITHUB_BASE_URL = "https://api.github.com"

# Allowed Github organizations
GITHUB_ORGS = list(
    filter(
        None,
        set(
            os.environ.get("GITHUB_ORGS", "").split(",")
            + [
                "ministryofjustice",
            ]
        ),
    )
)


# -- Elasticsearch

ELASTICSEARCH = {
    "hosts": [
        {
            "host": os.environ.get("ELASTICSEARCH_HOST"),
            "port": int(os.environ.get("ELASTICSEARCH_PORT", 9243)),
            "use_ssl": True,
            "http_auth": (
                os.environ.get("ELASTICSEARCH_USERNAME"),
                os.environ.get("ELASTICSEARCH_PASSWORD"),
            ),
        },
    ],
    "indices": {
        "s3-logs": os.environ.get(
            "ELASTICSEARCH_INDEX_S3LOGS",
            "s3logs-*",
        ),
        "app-logs": os.environ.get(
            "ELASTICSEARCH_INDEX_APPLOGS",
            f"{ENV}-node-*",
        ),
    },
}


# -- AWS
AWS_DATA_ACCOUNT_ID = os.environ.get("AWS_DATA_ACCOUNT_ID")
QUICKSIGHT_ACCOUNT_ID = os.environ.get("QUICKSIGHT_ACCOUNT_ID")
QUICKSIGHT_ACCOUNT_REGION = os.environ.get("QUICKSIGHT_ACCOUNT_REGION")
QUICKSIGHT_ASSUMED_ROLE = os.environ.get("QUICKSIGHT_ASSUMED_ROLE")

# The EKS OIDC provider, referenced in user policies to allow service accounts
# to grant AWS permissions.
OIDC_EKS_PROVIDER = os.environ.get("OIDC_EKS_PROVIDER")


# -- Slack
SLACK = {"api_token": os.environ.get("SLACK_API_TOKEN")}


# -- Structured logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json_formatter": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
        },
        "plain_console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
        },
        "key_value": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.KeyValueRenderer(
                key_order=["timestamp", "level", "event", "logger"]
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json_formatter",
        },
    },
    "loggers": {
        "django_structlog": {
            "handlers": [
                "console",
            ],
            "level": "INFO",
        },
        # Make sure to replace the following logger's name for yours
        "controlpanel": {
            "handlers": [
                "console",
            ],
            "level": "INFO",
        },
    },
}

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    context_class=structlog.threadlocal.wrap_dict(dict),
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# volume name for the EFS directory for user homes
EFS_VOLUME = os.environ.get("EFS_VOLUME")
MAX_RELEASE_NAME_LEN = 53


# Configure for celery for message queues
IAM_QUEUE_NAME = os.environ.get("IAM_QUEUE_NAME", "control-panel-iam")
S3_QUEUE_NAME = os.environ.get("S3_QUEUE_NAME", "control-panel-s3")
AUTH_QUEUE_NAME = os.environ.get("AUTH_QUEUE_NAME", "control-panel-auth")

BROKER_URL = os.environ.get("BROKER_URL", "sqs://")
DEFAULT_QUEUE = AUTH_QUEUE_NAME
DEFAULT_BACKOFF_POLICY = {1: 10, 2: 20, 3: 40, 4: 80, 5: 320, 6: 640}
PRE_DEFINED_QUEUES = [IAM_QUEUE_NAME, S3_QUEUE_NAME, AUTH_QUEUE_NAME]
CELERY_DEFAULT_QUEUE = DEFAULT_QUEUE
SQS_REGION = os.environ.get("SQS_REGION", "eu-west-2")
BROKER_TRANSPORT_OPTIONS = {
    "polling_interval": 1,
    "region": SQS_REGION,
    "wait_time_seconds": 0,
    "predefined_queues": {},
}
for queue in PRE_DEFINED_QUEUES:
    BROKER_TRANSPORT_OPTIONS["predefined_queues"][queue] = {
        "url": f"https://sqs.{SQS_REGION}.amazonaws.com/{AWS_DATA_ACCOUNT_ID}/{queue}",
        "backoff_policy": DEFAULT_BACKOFF_POLICY,
    }

CELERY_IMPORTS = ["controlpanel.api.tasks.handlers"]
DPR_DATABASE_NAME = os.environ.get("DPR_DATABASE_NAME", None)

S3_ARCHIVE_BUCKET_NAME = "dev-archive-folder"
