# Running directly on your machine


## Dependencies

The Control Panel app requires Python 3.6.5+

Install python dependencies with the following command:
```sh
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```


## Kubernetes setup

You need a kubeconfig (~/.kube/config) with the credentials for your k8s cluster. Once you've got that, this should work:
```sh
kubectl cluster-info
```


## Helm

You need to tell Helm to use the Analytical Platform chart repository:
```sh
helm repo add mojanalytics http://moj-analytics-helm-repo.s3-website-eu-west-1.amazonaws.com
helm repo update
```


## <a name="env"></a>Environment variables

At a mininum, you need to set the following environment variable:
```sh
export DJANGO_SETTINGS_MODULE=controlpanel.settings.development
```

See [Environment Variables Reference](doc/environment.md) for details of other
environment variable settings.


## Database

The Control Panel app connects to a PostgreSQL database, which should have a database with the expected name:
```sh
createuser -d controlpanel
createdb -U controlpanel controlpanel
```

Then you can run migrations:
```sh
python3 manage.py migrate
```


## Create superuser (on first run only)

```sh
python3 manage.py createsuperuser
```
NB `Username` needs to be your GitHub username


## Compile Sass and Javascript

Before the first run (or after changes to static assets), you need to run
```sh
python3 manage.py collectstatic
```


### Run the app

You can run the app with the Django development server with
```sh
python3 manage.py runserver
```
Or with Gunicorn WSGI server:
```sh
gunicorn -b 0.0.0.0:8000 controlpanel.wsgi:application
```
Go to http://localhost:8000/


### How to run the tests

```sh
make test
```
