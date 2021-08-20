import logging
from django.contrib import messages


class MigrateAlertMiddleware:
    """
    Middleware to check if the user is in a pending migration state. If so,
    every response will have an info message attached to it telling them they
    should migrate to the new platform.

    This simply piggy-backs upon the existing Django based alert system and is
    relatively easy to switch off via the MIDDLEWARE list in the settings.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, "user") and request.user.is_authenticated:
            if user.migration_state == user.PENDING:
                messages.info(
                    "Please migrate to the new platform..!"
                )
        return self.get_response(request)

