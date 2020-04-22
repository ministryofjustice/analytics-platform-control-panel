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

To run a Kubernetes cluster locally, the most convenient solution is probably
`minikube`. Follow the
[installation instructions for your OS](https://kubernetes.io/docs/tasks/tools/install-minikube/)
and check you have something working:

```
$ minikube status
m01
host: Running
kubelet: Running
apiserver: Running
kubeconfig: Configured
```

You'll need a kubeconfig file (`~/.kube/config`) with the credentials for your
kubernetes cluster. Starting `minikube` (e.g.
`minikube start --driver=virtualbox`) should create these credentials for you
for your local machine.

You can check things are working with the following command, which will return
information about the k8s master and KubeDNS:

```sh
kubectl cluster-info
```


## Helm

Install Helm (the K8s package manager) by following
[these instructions for your OS](https://helm.sh/docs/intro/install/).

You'll need to initialise Helm too:

```sh
helm init
```

Tell Helm to use the Analytical Platform chart repository:

```sh
helm repo add mojanalytics http://moj-analytics-helm-repo.s3-website-eu-west-1.amazonaws.com
helm repo update
```


## <a name="env"></a>Environment variables

The simplest solution is to ask for a copy of a working `.env` file from one of
the other developers with the envars set for development.

If this isn't immediately possible and at a mininum, you need to set the
following environment variables:

```sh
export DJANGO_SETTINGS_MODULE=controlpanel.settings.development
export SLACK_API_TOKEN=a_slack_token
```

See [Environment Variables Reference](environment.md) for details of other
environment variable settings.

The [Slack token](https://slack.dev/python-slackclient/auth.html) need not be
valid unless you'll be using the Slack related aspects of the system.


## Database

The Control Panel app connects to a PostgreSQL database called `controlpanel`,
which should be accessible with the `controlpanel` user.

Assuming you've got PostreSQL set up properly, the following commands should
get you to this state:

```sh
createuser -d controlpanel
createdb -U controlpanel controlpanel
```

Alternatively, if you prefer to use `psql` the following should work:

```
sudo -u postgres psql
postgres=# create database controlpanel;
postgres=# create user controlpanel with encrypted password 'password';
postgres=# grant all privileges on database controlpanel to controlpanel;
```

You must make sure the following environment variables are set:

```sh
export DB_USER=controlpanel
export DB_PASSWORD=password
```

Then you can run migrations:

```sh
python3 manage.py migrate
```


## Create superuser (on first run only)

```sh
python3 manage.py createsuperuser
```

Your `Username` needs to be your GitHub username.
Your `Auth0 id` needs to be ??? (not working for me yet).


## Compile Sass and Javascript

Before the first run (or after changes to static assets), you need to compile
and collate the static assets.

Static assets are compiled with Node.JS 8.16.0+

```sh
npm install
cp -R node_modules/accessible-autocomplete/dist/ static/accessible-autocomplete
cp -R node_modules/govuk-frontend/ static/govuk-frontend
cp -R node_modules/@ministryofjustice/frontend/ static/ministryofjustice-frontend
cp -R node_modules/html5shiv/dist/ static/html5-shiv
cp -R node_modules/jquery/dist/ static/jquery
./node_modules/.bin/babel \
  controlpanel/frontend/static/module-loader.js \
  controlpanel/frontend/static/components \
  controlpanel/frontend/static/javascripts \
  -o static/app.js -s
./node_modules/.bin/node-sass \
  --include-path node_modules/ \
  -o static/ \
  --output-style compact \
  controlpanel/frontend/static/app.scss
```

Then run collectstatic:
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
gunicorn -b 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker -w 4 controlpanel.asgi:application
```
Go to http://localhost:8000/


### How to run the tests

```sh
make test
```

or directly using `pytest`:

```sh
DJANGO_SETTINGS_MODULE=controlpanel.settings.test pytest
```

**NOTE** Set the `DJANGO_SETTINGS_MODULE` is important or otherwise you
may accidentally run the tests with the `development` settings with
unpredictable results.
