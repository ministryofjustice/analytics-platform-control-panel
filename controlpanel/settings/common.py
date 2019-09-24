import os
from os.path import abspath, dirname, join
import sys

from controlpanel.frontend.jinja2 import environment
from controlpanel.utils import is_truthy


# -- Feature flags

ENABLED = {

    # Enable Kubernetes Role-based Access Control
    "k8s_rbac": is_truthy(os.environ.get("ENABLE_K8S_RBAC", False)),

    # Enable writes to Kubernetes cluster
    "write_to_cluster": is_truthy(os.environ.get("ENABLE_WRITE_TO_CLUSTER", True)),

    # Enable redirecting legacy API URLs to new API app
    "redirect_legacy_api_urls": is_truthy(os.environ.get("ENABLE_LEGACY_API_REDIRECT", True)),
}

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
    # Django channels for asynchronous support
    "channels",
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
    # Django collect static files into a single location
    "django.contrib.staticfiles",
    # Make current request available anywhere
    "crequest",
    # Provides shell_plus, runserver_plus, etc
    "django_extensions",
    # Provides filter backend for use with Django REST Framework
    "django_filters",
    # Django REST Framework
    "rest_framework",
    # Sentry error tracking
    "raven.contrib.django.raven_compat",
    # Django Rules object permissions
    "rules",
    # Analytics Platform Control Panel API
    "controlpanel.api",
    # Analytics Platform Control Panel Kubernetes API proxy
    "controlpanel.kubeapi",
    # Analytics Platform Control Panel Frontend
    "controlpanel.frontend",
    # Health check
    "health_check",
    "health_check.db",
    "health_check.cache",
    "health_check.storage",
]

MIDDLEWARE = [
    "controlpanel.middleware.LegacyAPIRedirectMiddleware",
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
    'rules.permissions.ObjectPermissionBackend',
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
LOGIN_REDIRECT_URL_FAILURE = "/"

# Length of time it takes for an OIDC ID token to expire (default 15m)
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 15 * 60

# Gracefully handle state mismatch
OIDC_CALLBACK_CLASS = 'controlpanel.oidc.StateMismatchHandler'

# Hostname of the OIDC provider
OIDC_DOMAIN = os.environ.get("OIDC_DOMAIN")

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

OIDC_RP_SCOPES = "openid email profile offline-access"

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
}

OIDC_DRF_AUTH_BACKEND = "controlpanel.oidc.OIDCSubAuthenticationBackend"


# -- Security

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")

# A list of people who get code error notifications when DEBUG=False
ADMINS = []

# A list of people who get broken link notifications when
# BrokenLinkEmailsMiddleware is enabled
MANAGERS = []

# Whitelist values for the HTTP Host header, to prevent certain attacks
ALLOWED_HOSTS = [host for host in os.environ.get("ALLOWED_HOSTS", "").split() if host]


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
DEBUG = is_truthy(os.environ.get("DEBUG", False))


# -- Database

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", PROJECT_NAME),
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

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

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Token authentication
        "controlpanel.api.jwt_auth.JWTAuthentication",
        "mozilla_django_oidc.contrib.drf.OIDCAuthentication",
        # required for browsable API
        'rest_framework.authentication.BasicAuthentication',
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": ["controlpanel.api.filters.SuperusersOnlyFilter"],
    "DEFAULT_PERMISSION_CLASSES": ["controlpanel.api.permissions.IsSuperuser"],
    "DEFAULT_PAGINATION_CLASS": "controlpanel.api.pagination.CustomPageNumberPagination",
    "PAGE_SIZE": 100,
}


# -- Logging

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s %(name)s %(levelname)s %(message)s"}
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": os.environ.get("LOG_LEVEL", "DEBUG"),
        },
        "aioredis": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "asyncio": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "botocore": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "daphne": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "elasticsearch": {
            "handlers": ['console'],
            "level": "WARNING",
        },
        "github": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "gunicorn": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "kubernetes": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "mozilla_django_oidc": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "requests_oauthlib": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "rules": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "urllib3": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "uvicorn": {
            "handlers": ["console"],
            "level": "WARNING",
        },
    },
}


# -- Sentry error tracking

if os.environ.get("SENTRY_DSN"):
    RAVEN_CONFIG = {
        "dsn": os.environ.get("SENTRY_DSN", ""),
        "environment": os.environ.get("ENV", "dev"),
        "ignore_exceptions": [],
    }
    if "shell" in sys.argv or "shell_plus" in sys.argv:
        RAVEN_CONFIG["ignore_exceptions"] = ["*"]

else:
    INSTALLED_APPS.remove("raven.contrib.django.raven_compat")


# -- Static files

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]


# -- What's new

WHATS_NEW_URL = (
    "https://raw.githubusercontent.com/moj-analytical-services/"
    "platform_user_guidance/master/changelog/whats_new.md"
)


# -- Tool deployments

TOOLS = {
    "rstudio": {
        "domain": os.environ.get("RSTUDIO_AUTH_CLIENT_DOMAIN", OIDC_DOMAIN),
        "client_id": os.environ.get("RSTUDIO_AUTH_CLIENT_ID"),
        "client_secret": os.environ.get("RSTUDIO_AUTH_CLIENT_SECRET"),
    },
    "jupyter-lab": {
        "domain": os.environ.get("JUPYTER_LAB_AUTH_CLIENT_DOMAIN", OIDC_DOMAIN),
        "client_id": os.environ.get("JUPYTER_LAB_AUTH_CLIENT_ID"),
        "client_secret": os.environ.get("JUPYTER_LAB_AUTH_CLIENT_SECRET"),
    },
    "airflow-sqlite": {
        "domain": os.environ.get("AIRFLOW_AUTH_CLIENT_DOMAIN", OIDC_DOMAIN),
        "client_id": os.environ.get("AIRFLOW_AUTH_CLIENT_ID"),
        "client_secret": os.environ.get("AIRFLOW_AUTH_CLIENT_SECRET"),
    },
}

# Helm repo where tool charts are hosted
HELM_REPO = os.environ.get('HELM_REPO', 'mojanalytics')

# domain where tools are deployed
TOOLS_DOMAIN = os.environ.get('TOOLS_DOMAIN')

# hostname of NFS server for user homes
NFS_HOSTNAME = os.environ.get("NFS_HOSTNAME")


# -- Redis
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
REDIS_PORT = os.environ.get('REDIS_PORT', '6379')

# -- Async

ASGI_APPLICATION = f"{PROJECT_NAME}.routing.application"

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [{'address': (REDIS_HOST, REDIS_PORT)}],
        },
    },
}
if REDIS_PASSWORD:
    CHANNEL_LAYERS['default']['CONFIG']['hosts'][0]['password'] = REDIS_PASSWORD


# -- Github

# Allowed Github organizations
GITHUB_ORGS = list(filter(
    None,
    set(os.environ.get("GITHUB_ORGS", "").split(",") + [
        # 'ministryofjustice',
        'moj-analytical-services',
    ]),
))


# -- Elasticsearch

ELASTICSEARCH = {
    'hosts': [
        {
            'host': os.environ.get('ELASTICSEARCH_HOST'),
            'port': int(os.environ.get('ELASTICSEARCH_PORT', 9243)),
            'use_ssl': True,
            'http_auth': (
                os.environ.get('ELASTICSEARCH_USERNAME'),
                os.environ.get('ELASTICSEARCH_PASSWORD')
            ),
        },
    ],
    'indices': {
        's3-logs': os.environ.get(
            'ELASTICSEARCH_INDEX_S3LOGS',
            's3logs-*',
        ),
        'app-logs': os.environ.get(
            'ELASTICSEARCH_INDEX_APPLOGS',
            f'logstash-apps-{ENV}-*',
        ),
    },
}

KIBANA_BASE_URL = os.environ.get(
    KIBANA_BASE_URL,
    f'https://kibana.services.{{ENV}}.mojanalytics.xyz/app/kibana',
)


# -- AWS
AWS_ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID')
K8S_WORKER_ROLE_NAME = os.environ.get('K8S_WORKER_ROLE_NAME')

BUCKET_REGION = os.environ.get('BUCKET_REGION', 'eu-west-1')

# Auth0 integrated SAML provider, referenced in user policies to allow login via
# SAML federation
SAML_PROVIDER = os.environ.get('SAML_PROVIDER')

# Name of S3 bucket where logs are stored
LOGS_BUCKET_NAME = os.environ.get('LOGS_BUCKET_NAME', 'moj-analytics-s3-logs')


# -- Airflow
AIRFLOW_SECRET_KEY = os.environ.get('AIRFLOW_SECRET_KEY')
AIRFLOW_FERNET_KEY = os.environ.get('AIRFLOW_FERNET_KEY')
