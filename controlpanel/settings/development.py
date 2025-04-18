# Standard library
import os

# First-party/Local
from controlpanel.settings.common import *

# Enable debugging
DEBUG = True

# Allow all hostnames to access the server
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]
QUICKSIGHT_DOMAINS = ["http://localhost:8000"]

# Enable Django debug toolbar
if os.environ.get("ENABLE_DJANGO_DEBUG_TOOLBAR"):
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405, E501
    INSTALLED_APPS.extend(["debug_toolbar"])  # noqa: F405, E501
    DEBUG_TOOLBAR_PANELS = [
        "debug_toolbar.panels.versions.VersionsPanel",
        "debug_toolbar.panels.timer.TimerPanel",
        "debug_toolbar.panels.settings.SettingsPanel",
        "debug_toolbar.panels.headers.HeadersPanel",
        "debug_toolbar.panels.request.RequestPanel",
        "debug_toolbar.panels.sql.SQLPanel",
        "debug_toolbar.panels.staticfiles.StaticFilesPanel",
        # Jinja2 not supported
        # 'debug_toolbar.panels.templates.TemplatesPanel',
        "debug_toolbar.panels.cache.CachePanel",
        "debug_toolbar.panels.signals.SignalsPanel",
        "debug_toolbar.panels.logging.LoggingPanel",
        "debug_toolbar.panels.redirects.RedirectsPanel",
    ]

INTERNAL_IPS = ["127.0.0.1"]

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# -- Structured logging
LOGGING["loggers"]["controlpanel"]["level"] = "INFO"  # noqa: F405

DASHBOARD_SERVICE_DOMAINS = ["http://localhost:8001"]
