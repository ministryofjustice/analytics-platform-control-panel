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
| `SECRET_KEY` | | |
| `DEBUG` | | `False` |
| `ALLOWED_HOSTS` | Space separated. Must be set if DEBUG is False | |
| `BUCKET_REGION` | | `eu-west-1` |
| `ENV` | | `dev` |
| `LOGS_BUCKET_NAME` | | `moj-analytics-s3-logs` |
| `IAM_ARN_BASE` | | |
| `K8S_WORKER_ROLE_NAME` | | |
| `SAML_PROVIDER_ARN` | | |
| `SENTRY_DSN` | | |
| `OIDC_CLIENT_ID` | | |
| `OIDC_CLIENT_SECRET` | | |
| `OIDC_DOMAIN` | | |
| `DB_NAME` | | `controlpanel` |
| `DB_USER` | | |
| `DB_PASSWORD` | | |
| `DB_HOST` | | `127.0.0.1` |
| `DB_PORT` | | `5432` |

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
