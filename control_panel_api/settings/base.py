import os


def is_enabled(value):
    return str(value).lower() not in ('n', 'no', 'off', 'false', '0')


# These are boolean flags to enable/disable features in the API
ENABLED = {
    'k8s_rbac': is_enabled(os.environ.get('ENABLE_K8S_RBAC', False)),
    'write_to_cluster':
        is_enabled(os.environ.get('ENABLE_WRITE_TO_CLUSTER', True)),
}

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    '(2gbfi1uc1llww251t00s7$^luuzvivf7l+(snj=sbt#s8h!wu')

# SECURITY WARNING: don't run with debug turned on in production!
# Override this in your environment or local settings
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Whitelist values for the HTTP Host header, to prevent certain attacks
# MUST be set if DEBUG is False
ALLOWED_HOSTS = list(
    filter(None, os.environ.get('ALLOWED_HOSTS', '').split(' ')))

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Application definition

INSTALLED_APPS = [
    # 'django.contrib.admin',  # do we need this?
    'django.contrib.auth',  # User and Group stuff
    'django.contrib.contenttypes',  # used by auth
    'django.contrib.sessions',
    # 'django.contrib.messages',
    'django.contrib.staticfiles',  # TODO - remove this?
    'django_extensions',
    'django_filters',
    'rest_framework',
    'rest_framework_swagger',
    'raven.contrib.django.raven_compat',
    'control_panel_api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # TODO - remove?
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # TODO - remove?
]

ROOT_URLCONF = 'control_panel_api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                # 'django.template.context_processors.i18n',
                # 'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                # 'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'control_panel_api.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'controlpanel'),
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = []

AUTH_USER_MODEL = 'control_panel_api.User'

# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-gb'

TIME_ZONE = 'UTC'

USE_I18N = False

USE_L10N = False

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_ROOT = os.path.join(BASE_DIR, 'static/')

STATIC_URL = '/static/'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'control_panel_api.authentication.Auth0JWTAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication'
    ],
    'DEFAULT_FILTER_BACKENDS': ('control_panel_api.filters.SuperusersOnlyFilter',),
    'DEFAULT_PERMISSION_CLASSES': [
        'control_panel_api.permissions.IsSuperuser',
    ],
    'DEFAULT_PAGINATION_CLASS': 'control_panel_api.pagination.CustomPageNumberPagination',
    'PAGE_SIZE': 100
}

LOGIN_URL = 'rest_framework:login'
LOGOUT_URL = 'rest_framework:logout'

# AWS variables
BUCKET_REGION = os.environ.get('BUCKET_REGION', 'eu-west-1')
ENV = os.environ.get('ENV', 'dev')
LOGS_BUCKET_NAME = os.environ.get('LOGS_BUCKET_NAME', 'moj-analytics-s3-logs')
IAM_ARN_BASE = os.environ.get('IAM_ARN_BASE', '')
K8S_WORKER_ROLE_NAME = os.environ.get('K8S_WORKER_ROLE_NAME', '')
SAML_PROVIDER = os.environ.get('SAML_PROVIDER', '')

RAVEN_CONFIG = {
    'dsn': os.environ.get('SENTRY_DSN', ''),
    'environment': ENV,
}

OIDC_CLIENT_ID = os.environ.get('OIDC_CLIENT_ID')
OIDC_CLIENT_SECRET = os.environ.get('OIDC_CLIENT_SECRET')
OIDC_DOMAIN = os.environ.get('OIDC_DOMAIN')
OIDC_FIELD_USERNAME = 'nickname'
OIDC_FIELD_EMAIL = 'email'
OIDC_FIELD_NAME = 'name'
OIDC_WELL_KNOWN_URL = f'https://{OIDC_DOMAIN}/.well-known/jwks.json'
OIDC_AUTH_EXTENSION_URL = os.environ.get('OIDC_AUTH_EXTENSION_URL')
OIDC_AUTH_EXTENSION_AUDIENCE = os.environ.get('OIDC_AUTH_EXTENSION_AUDIENCE', 'urn:auth0-authz-api')

# Helm variables
NFS_HOSTNAME = os.environ.get('NFS_HOSTNAME')
TOOLS_DOMAIN = os.environ.get('TOOLS_DOMAIN')
# RStudio tool - Auth client config
RSTUDIO_AUTH_CLIENT_DOMAIN = os.environ.get('RSTUDIO_AUTH_CLIENT_DOMAIN', OIDC_DOMAIN)
RSTUDIO_AUTH_CLIENT_ID = os.environ.get('RSTUDIO_AUTH_CLIENT_ID')
RSTUDIO_AUTH_CLIENT_SECRET = os.environ.get('RSTUDIO_AUTH_CLIENT_SECRET')

ELASTICSEARCH = {
    'connection': {
        'host': os.environ.get('ELASTICSEARCH_HOST'),
        'port': os.environ.get('ELASTICSEARCH_PORT', 9243),
        'http_auth': (
            os.environ.get('ELASTICSEARCH_USERNAME'),
            os.environ.get('ELASTICSEARCH_PASSWORD')
        ),
    },
    'index': os.environ.get('ELASTICSEARCH_INDEX_S3LOGS', 's3logs-*'),
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': os.environ.get('LOG_LEVEL', 'DEBUG'),
        },
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('LOG_LEVEL', 'DEBUG'),
        },
    },
}
