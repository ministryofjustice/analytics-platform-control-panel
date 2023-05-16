# Third-party
from django_prometheus.conf import NAMESPACE
from prometheus_client import Counter

login_events = Counter(
    "django_control_panel_login_events",
    "Counter of login events",
    ["model"],
    namespace=NAMESPACE,
)
