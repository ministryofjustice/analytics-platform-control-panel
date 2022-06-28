# Environment Variables Reference

| Name | Description | Default |
| ---- | ----------- | ------- |
| `ALLOWED_HOSTS` | Space separated. Must be set if DEBUG is False | `[]` |
| `ALLOWED_HOSTS` | Space separated. Must be set if DEBUG is False | `[]` |
| `AWS_COMPUTE_ACCOUNT_ID` | ID of the AWS account where tools and apps run | |
| `AWS_DATA_ACCOUNT_ID` | ID of the AWS account where data sits | |
| `BUCKET_REGION` | AWS region | `eu-west-1` |
| `DB_HOST` | Hostname of postgres server | `127.0.0.1` |
| `DB_NAME` | Postgres database name | `controlpanel` |
| `DB_PASSWORD` | Postgres password | |
| `DB_PORT` | Postgres port | `5432` |
| `DB_USER` | Postgres username | |
| `DEBUG` | Run in debug mode, displaying stacktraces on errors, etc | `False` |
| `EFS_HOSTNAME` | Hostname of EFS server for user homes | |
| `EFS_VOLUME` | volume name for the EFS directory for user homes | |
| `EKS` | Flag to indicate the application is running on EKS infrastructure | |
| `ELASTICSEARCH_HOST` | | |
| `ELASTICSEARCH_INDEX_S3LOGS` | | `s3logs-*` |
| `ELASTICSEARCH_PASSWORD` | | |
| `ELASTICSEARCH_PORT` | | `9243` |
| `ELASTICSEARCH_USERNAME` | | |
| `ENV` | Environment name - either `dev` or `alpha` | `dev` |
| `GITHUB_ORGS` | Comma-separated list of Github organisations searched for webapp repositories |
| `GOOGLE_ANALYTICS_ID` | Key for Google Analytics account | |
| `HELM_REPOS` | Helm repository where the tool charts are hosted | `mojanalytics` |
| `K8S_WORKER_ROLE_NAME` | the name of the IAM role assigned to Kubernetes nodes, e.g. `nodes.dev.mojanalytics.xyz`. Combined with the ARN base to generate a full ARN like `arn:aws:iam::123456789012:role/nodes.dev.mojanalytics.xyz` | |
| `KIBANA_BASE_URL` | Kibana endpoint for Elastic logs | `https://kibana.services.{ENV}.mojanalytics.xyz/app/kibana` |
| `LOG_LEVEL` | The level of logging output - in increasing levels of verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `DEBUG` |
| `LOGS_BUCKET_NAME` | Name of S3 bucket where logs are stored | `moj-analytics-s3-logs` |
| `OIDC_AUTH_EXTENSION_URL` | Base URL of Auth0 authorization API | |
| `OIDC_CLIENT_ID` | Client ID from Auth0 | |
| `OIDC_CLIENT_SECRET` | Client secret from Auth0 | |
| `OIDC_DOMAIN` | Domain of Auth0 tenant | |
| `OIDC_EKS_PROVIDER` | Equivalent of SAML_PROVIDER but for the app running on EKS infrastructure | |
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
| `SLACK_API_TOKEN` | Slack token ([more information)](https://slack.dev/python-slackclient/auth.html) | Only required when you're working with Slack |
| `SLACK_CHANNEL` | The channel to where Slack messages are to be posted | `#analytical-platform` |
| `TOOLS_DOMAIN` | Domain where tools are deployed | |
| `APP_DOMAIN` | Domain where users' applications are deployed | |
| `USER_GUIDANCE_BASE_URL` | Domain where user guidance is found | |
