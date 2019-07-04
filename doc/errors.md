# Error explanations


    Error: file "mojanalytics/rstudio" not found

It ran a Helm command but it can't find the chart. See [Helm set-up](helm.md).

---

    django.core.exceptions.ImproperlyConfigured: Requested setting DATABASES, but settings are not configured. You must either define the environment variable DJANGO_SETTINGS_MODULE or call settings.configure() before accessing settings.

You need to [set environment variable `DJANGO_SETTINGS_MODULE`](environment.md).

---

    400 : ["The schema generator did not return a schema Document"]

You need to log in.

---

    kubernetes.config.config_exception.ConfigException: Service host/port is not set.

Your Kubernetes access token has expired. You can refresh it by running `kubectl
cluster-info`.

---
