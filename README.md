# analytics-platform-control-panel
Control panel contains admin functions like creating users and granting access to apps


## Running with Docker

```sh
docker-compose build
docker-compose up
```
and then in a separate terminal window,
```sh
docker-compose exec app python3 manage.py createsuperuser
```
Then browse to http://localhost:8000/

### Running tests with docker

```sh
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

## Running directly on your machine

### Dependencies

The Control Panel app requires Python 3.6+

It is best to use a virtual environment to install dependencies, eg:
```sh
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

### <a name="env"></a>Environment variables

| name | description | default |
| ---- | ----------- | ------- |
| `SECRET_KEY` | Secret key used to encrypt cookies, etc | |
| `DEBUG` | Run in debug mode, displaying stacktraces on errors, etc | `False` |
| `ALLOWED_HOSTS` | Space separated. Must be set if DEBUG is False | |
| `BUCKET_REGION` | AWS region | `eu-west-1` |
| `ENV` | Environment name - either `dev` or `alpha` | `dev` |
| `LOGS_BUCKET_NAME` | Name of S3 bucket where logs are stored | `moj-analytics-s3-logs` |
| `IAM_ARN_BASE` | the initial part of the canonical reference ID to an IAM resource. e.g. given a full ARN of `arn:aws:iam::123456789012:role/Admin`, the ARN base is `arn:aws:iam::123456789012` | |
| `K8S_WORKER_ROLE_NAME` | the name of the IAM role assigned to Kubernetes nodes, e.g. `nodes.dev.mojanalytics.xyz`. Combined with the ARN base to generate a full ARN like `arn:aws:iam::123456789012:role/nodes.dev.mojanalytics.xyz` | |
| `SAML_PROVIDER` | the name of the SAML provider within AWS, which Auth0 integrates with, e.g. `dev-auth0`. This is referenced in user policies to allow them to log in via SAML federation. | |
| `SENTRY_DSN` | Sentry credentials | |
| `OIDC_CLIENT_ID` | Client ID from Auth0 | |
| `OIDC_CLIENT_SECRET` | Client secret from Auth0 | |
| `OIDC_DOMAIN` | Domain of Auth0 tenant | |
| `DB_NAME` | Postgres database name | `controlpanel` |
| `DB_USER` | Postgres username | |
| `DB_PASSWORD` | Postgres password | |
| `DB_HOST` | Hostname of postgres server | `127.0.0.1` |
| `DB_PORT` | Postgres port | `5432` |

### Database

The Control Panel app connects to a PostgreSQL database, which should have a database with the expected name:
```sh
createdb $DB_NAME
```

Then you can run migrations:
```sh
python manage.py migrate
```

### Create superuser (on first run only)

```sh
python manage.py createsuperuser
```

### Compile Sass and Javascript

Before the first run (or after changes to static assets), you need to run
```sh
python manage.py collectstatic
```

### Run the app

You can run the app with
```sh
./run_api
```
Go to http://localhost:8000/

### How to run the tests

```sh
./run_tests
```


# Documentation

You can see the documentation and interact with the API by visiting [http://localhost:8000/](http://localhost:8000/).
