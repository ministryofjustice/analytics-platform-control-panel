# analytics-platform-control-panel
Control panel contains admin functions like creating users and granting access to apps


# Config

## Create database

```sh
createdb controlpanel
```

## Set environment variables

```sh
export DB_NAME=controlpanel
```

## Run migrations

```sh
python manage.py migrate
```

## Create superuser (on first run only)

```sh
python manage.py createsuperuser
```

## Run server

```sh
python manage.py runserver
```

Go to http://localhost:8000/
