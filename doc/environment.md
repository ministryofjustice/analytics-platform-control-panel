# The Settings and Environment Variables Reference

There are several ways to set up the settings required for running this app which
are explained in the following sub sections

## Django settings 
Official guide [here](https://docs.djangoproject.com/en/4.0/topics/settings/)
In general, all system level settings related to important app logic are defined here,
it is the primary entry point for defining global settings. An app normally has different
running modes:
- development mode: for local development.
- testing mode: for automated testing.
- production mode: for production use. Usually when the app runs on non-local env, the running mode will be production regardless which cluster environment is used for running this app.

You can define different .py files for mapping different running modes under `/settings/`. For this app, we did not
define a specific file for production mode. We are responsible to pass correct value to the django
environment variable `DJANGO_SETTINGS_MODULE` under different running environments(e.g., dev, staging and
prod).

Whether or not a variable can be overwritten by an environment variable is up to the implementation in `settings/*.py`

## settings.yaml
We also introduce this file to allow us to define some variables which are required to be secured but may have
different values under different running environments and slightly more complicated logic such as feature flags.
Also this yaml can give us easy option to define some simple constants.

This file is on the top of django settings, so the variables which define in the settings/*.py has higher
priority than the ones in the settings.yaml. If the same variable has been defined in the django settings file, the same one in 
the settings.yaml will be ignored

The format for defining a variable with different value under different envs
```yaml
<The name of variable>:
  _DEFAULT: <The default value>
  _HOST_<settings.ENV>: <The value under specific env>
```
The example is below
```yaml
TESTING_VALUE:
  _HOST_dev: 'DEV'
  _HOST_prod: 'PROD'
  _HOST_alpha: 'ALPHA'

```

All those variables in this file can be overwritten by the environment variable if needed.

## environment variables

The variables defined below are the minimum ones which are required to be provided. As being
mentioned from previous sections, you can overwrite any variable in settings.yaml, some of them 
in django settings. 

| Name | Description | Default |
| ---- | ----------- | ------- |
| `ALLOWED_HOSTS` | Space separated. Must be set if DEBUG is False | `[]` |
| `AWS_COMPUTE_ACCOUNT_ID` | ID of the AWS account where tools and apps run | |
| `AWS_DATA_ACCOUNT_ID` | ID of the AWS account where data sits | |
| `DB_HOST` | Hostname of postgres server | `127.0.0.1` |
| `DB_NAME` | Postgres database name | `controlpanel` |
| `DB_PASSWORD` | Postgres password | |
| `DB_PORT` | Postgres port | `5432` |
| `DB_USER` | Postgres username | |
| `DEBUG` | Run in debug mode, displaying stacktraces on errors, etc | `False` |
| `EFS_VOLUME` | volume name for the EFS directory for user homes | |
| `ELASTICSEARCH_HOST` | | |
| `ELASTICSEARCH_INDEX_S3LOGS` | | `s3logs-*` |
| `ELASTICSEARCH_PASSWORD` | | |
| `ELASTICSEARCH_PORT` | | `9243` |
| `ELASTICSEARCH_USERNAME` | | |
| `ENV` | Environment name - either `dev` or `alpha` | `dev` |
| `GITHUB_ORGS` | Comma-separated list of Github organisations searched for webapp repositories |
| `GOOGLE_ANALYTICS_ID` | Key for Google Analytics account | |
| `HELM_REPOS` | Helm repository where the tool charts are hosted | `mojanalytics` |
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
| `SKIP_DB_SSL` | Optional: Decide whether the DB connectioin require ssl | Default is True for local env but False for cloud env |
