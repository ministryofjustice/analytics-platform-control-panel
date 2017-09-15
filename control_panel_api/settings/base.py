import os

import boto3

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
    'rest_framework',
    'rest_framework_swagger',
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
    'DEFAULT_FILTER_BACKENDS': ('control_panel_api.filters.SuperusersOnlyFilter',),
    'DEFAULT_PERMISSION_CLASSES': [
        'control_panel_api.permissions.IsSuperuser',
    ],
    'PAGE_SIZE': 10
}

LOGIN_URL = 'rest_framework:login'
LOGOUT_URL = 'rest_framework:logout'

# AWS variables
BUCKET_REGION = os.environ.get('BUCKET_REGION', 'eu-west-1')
ENV = os.environ.get('ENV', 'dev')
LOGS_BUCKET_NAME = os.environ.get('LOGS_BUCKET_NAME', 'moj-analytics-s3-logs')
IAM_ARN_BASE = os.environ.get('IAM_ARN_BASE', '')
K8S_WORKER_ROLE_ARN = os.environ.get('K8S_WORKER_ROLE_ARN', '')

AWS_API_CLIENT_HANDLER = boto3.client
