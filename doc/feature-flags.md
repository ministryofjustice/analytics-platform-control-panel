# Feature Flags

Some of the Control Panel's features are enabled/disabled via flags in `settings.yaml`
[Settings and environment variables](environment.md). This is to allow easy concurrent feature development.

In order to define a feature_flag, the following format need to be used:
```
enabled_features:
  <feature flag name>:
    _DEFAULT: <true/false>
    _HOST_<settings.ENV>: <true/false>
```
for example 
```
enabled_features:
  ip_ranges:
    _DEFAULT: true
    _HOST_dev: true
    _HOST_prod: false

```
The code for checking whether feature flag has been set or not under current running environment
e.g., dev or prod is below
```
from django.conf import settings

settings.features.ip_ranges.enabled
```
