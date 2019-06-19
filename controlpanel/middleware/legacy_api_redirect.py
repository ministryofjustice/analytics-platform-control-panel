import logging
import re

from django.conf import settings


API_PATH = re.compile(r'^/(?P<resource>[^/]+)')

log = logging.getLogger(__name__)


class LegacyAPIRedirectMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.ENABLED["redirect_legacy_api_urls"]:
            json_requested = request.META.get("HTTP_ACCEPT") == "application/json"
            is_api_path = legacy_api_path(request.path_info)

            if is_api_path and json_requested:
                log.debug(f"Redirecting legacy API request: {request.path_info}")
                request.urlconf = "controlpanel.api.urls"

        return self.get_response(request)


def legacy_api_path(path):
    match = API_PATH.match(path)
    if match:
        return match.group('resource') in [
            'apps',
            'apps3buckets',
            'groups',
            's3buckets',
            'userapps',
            'users',
            'users3buckets',
            'tools',
        ]
