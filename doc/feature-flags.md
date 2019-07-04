# Feature Flags

Some of the Control Panel's features are enabled/disabled via flags in
[environment variables](environment.md). This is to allow easy concurrent feature development.

Current flags are:

| Name | Description | Default |
| ---- | ----------- | ------- |
| `ENABLE_K8S_RBAC` | Enable Kubernetes Role-based Access Control | `False` |
| `ENABLE_WRITE_TO_CLUSTER` | Enables writing changes to the Kubernetes cluster | `True` |
