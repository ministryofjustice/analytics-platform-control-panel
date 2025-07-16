# Standard library
import json

# Third-party
import structlog
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

# First-party/Local
from controlpanel.api.models.status_post import StatusPageEvent

log = structlog.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class PagerDutyWebhookView(View):

    def post(self, request, *args, **kwargs):
        if not self._validate_token(request):
            log.warning("pagerduty.invalid_token")
            return HttpResponseForbidden("Invalid token")

        data = self._parse_payload(request)
        if data is None:
            log.warning("pagerduty.invalid_json")
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        href = data.get("href")
        if not href:
            log.warning("pagerduty.missing_href")
            return HttpResponseBadRequest("Missing href in payload")

        event, created = self._save_event(data, href)

        log.info(
            "pagerduty.event_processed",
            action="created" if created else "updated",
            href=event.href,
            post_type=event.post_type,
            severity=event.severity,
            title=event.title,
        )

        return JsonResponse({"status": "ok", "action": "Created" if created else "Updated"})

    def _validate_token(self, request):
        return request.GET.get("token") == settings.PAGERDUTY_WEBHOOK_SECRET

    def _parse_payload(self, request):
        try:
            return json.loads(request.body)
        except json.JSONDecodeError:
            return None

    def _save_event(self, data, href):
        return StatusPageEvent.objects.update_or_create(
            href=href,
            defaults={
                "title": data.get("title", ""),
                "post_type": data.get("post_type", ""),
                "severity": data.get("severity", ""),
                "starts_at": (
                    parse_datetime(data.get("starts_at")) if data.get("starts_at") else None
                ),
                "ends_at": parse_datetime(data.get("ends_at")) if data.get("ends_at") else None,
                "raw_payload": data,
            },
        )
