# analytics-platform-control-panel
Control panel contains admin functions like creating users and granting access to apps

## How to run the tests

```sh
python manage.py test --settings=control_panel_api.settings.test
```


# Config

## Create database

```sh
createdb controlpanel
```

## Set environment variables

```sh
export DB_NAME=controlpanel
export DEBUG=true
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

# Documentation

You can see the documentation and interact with the API by visiting [http://localhost:8000/](http://localhost:8000/).
