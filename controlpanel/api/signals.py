# Third-party
from django.dispatch import receiver
from django_structlog.signals import bind_extra_request_metadata

# First-party/Local
from controlpanel.api.metrics import login_events


@receiver(bind_extra_request_metadata)
def bind_trace_id(request, logger, **kwargs):
    logger.bind(trace_id=request.headers.get("X-Amzn-Trace-Id", None))


def prometheus_login_event(sender, user, request, **kwargs):
    login_events.labels("user").inc()
