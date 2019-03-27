from controlpanel.settings.common import *


# Enable debugging
DEBUG = True

# Allow all hostnames to access the server
ALLOWED_HOSTS = "*"

# Reduce log level of Django internals
LOGGING["loggers"]["django"] = {"handlers": ["console"], "level": "WARNING"}

# Enable Django debug toolbar
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
INSTALLED_APPS.append("debug_toolbar")
INTERNAL_IPS = ['127.0.0.1']
