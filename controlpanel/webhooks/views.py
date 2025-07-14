# Standard library
import json

# Third-party
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

# First-party/Local
from controlpanel.api.models.status_post import StatusPageEvent


@csrf_exempt
def pagerduty_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    token = request.GET.get("token")
    if token != settings.PAGERDUTY_WEBHOOK_SECRET:
        return HttpResponseForbidden("Invalid token")

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    href = data.get("href")
    if not href:
        return HttpResponseBadRequest("Missing href in payload")

    event, created = StatusPageEvent.objects.update_or_create(
        href=href,
        defaults={
            "title": data.get("title", ""),
            "post_type": data.get("post_type", ""),
            "severity": data.get("severity", ""),
            "starts_at": parse_datetime(data.get("starts_at")) if data.get("starts_at") else None,
            "ends_at": parse_datetime(data.get("ends_at")) if data.get("ends_at") else None,
            "raw_payload": data,
        },
    )

    return JsonResponse({"status": "ok", "action": "Created" if created else "Updated"})
