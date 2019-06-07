# Environment Variables Reference

| Name | Description | Default |
| ---- | ----------- | ------- |
| `ALLOWED_HOSTS` | Space separated. Must be set if DEBUG is False | `[]` |
| `BUCKET_REGION` | AWS region | `eu-west-1` |
| `DB_HOST` | Hostname of postgres server | `127.0.0.1` |
| `DB_NAME` | Postgres database name | `controlpanel` |
| `DB_PASSWORD` | Postgres password | |
| `DB_PORT` | Postgres port | `5432` |
| `DB_USER` | Postgres username | |
| `DEBUG` | Run in debug mode, displaying stacktraces on errors, etc | `False` |
| `ELASTICSEARCH_HOST` | | |
| `ELASTICSEARCH_INDEX_S3LOGS` | | `s3logs-*` |
| `ELASTICSEARCH_PASSWORD` | | |
| `ELASTICSEARCH_PORT` | | `9243` |
| `ELASTICSEARCH_USERNAME` | | |
| `ENABLE_*` | See [Feature flags](doc/feature-flags.md) | |
| `ENV` | Environment name - either `dev` or `alpha` | `dev` |
| `GITHUB_ORGS` | Comma-separated list of Github organisations searched for
webapp repositories |
| `IAM_ARN_BASE` | the initial part of the canonical reference ID to an IAM resource. e.g. given a full ARN of `arn:aws:iam::123456789012:role/Admin`, the ARN base is `arn:aws:iam::123456789012` | |
| `K8S_WORKER_ROLE_NAME` | the name of the IAM role assigned to Kubernetes nodes, e.g. `nodes.dev.mojanalytics.xyz`. Combined with the ARN base to generate a full ARN like `arn:aws:iam::123456789012:role/nodes.dev.mojanalytics.xyz` | |
| `LOG_LEVEL` | The level of logging output - in increasing levels of verbosity:
`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `DEBUG` |
| `LOGS_BUCKET_NAME` | Name of S3 bucket where logs are stored | `moj-analytics-s3-logs` |
| `NFS_HOSTNAME` | Hostname of NFS server for user homes | |
| `OIDC_AUTH_EXTENSION_URL` | Base URL of Auth0 authorization API | |
| `OIDC_CLIENT_ID` | Client ID from Auth0 | |
| `OIDC_CLIENT_SECRET` | Client secret from Auth0 | |
| `OIDC_DOMAIN` | Domain of Auth0 tenant | |
| `OIDC_OP_AUTHORIZATION_ENDPOINT` | URL of OIDC Provider authorization endpoint | |
| `OIDC_OP_JWKS_ENDPOINT` | URL of OIDC Provider JWKS endpoint | |
| `OIDC_OP_TOKEN_ENDPOINT` | URL of OIDC Provider token endpoint | |
| `OIDC_OP_USER_ENDPOINT` | URL of OIDC Provider userinfo endpoint | |
| `OIDC_RP_SIGN_ALGO` | Algorithm to use for signing JWTs | `RS256` |
| `REDIS_HOST` | Hostname of Redis server | `localhost` |
| `REDIS_PORT` | Port number of Redis server | `6379` |
| `SAML_PROVIDER` | the name of the SAML provider within AWS, which Auth0 integrates with, e.g. `dev-auth0`. This is referenced in user policies to allow them to log in via SAML federation. | |
| `SECRET_KEY` | Secret key used to encrypt cookies, etc | |
| `SENTRY_DSN` | Sentry credentials | |
| `TOOLS_DOMAIN` | Domain where tools are deployed | |
| `*_AUTH_CLIENT_DOMAIN` | OIDC domain for tool instances | [`OIDC_DOMAIN`]() |
| `*_AUTH_CLIENT_ID` | OIDC client ID for tool instances | |
| `*_AUTH_CLIENT_SECRET` | OIDC client secret for tool instances | |
