# Running directly on your machine

There are essentially three aspects to getting the control panel in a state for
development on your local machine:

1. Ensuring you have all the required dependencies installed, and these are all
   correctly configured.
2. Getting hold of the source code for the project and creating a local
   environment in which to be able to work.
3. Acquiring the credentials and permissions needed for the various third-party
   aspects of the project (AWS, Auth0, k8s).

The third party services used by the application are labelled as either `dev`
(for use as part of the development / testing process) and `alpha` (which is
what our users use). Obviously, you should avoid using the `alpha` labelled
versions of the services.

## Required Dependencies

You must have [Redis](https://redis.io/),
[PostgreSQL](https://www.postgresql.org/), [npm](https://www.npmjs.com/) and
possibly [direnv](https://direnv.net/), [docker](https://www.docker.com/) and
[virtualbox](https://www.virtualbox.org/).
These should be installed using your own OS's package manager (`brew`, `apt`
etc...).

For [Kubernetes](https://kubernetes.io/) (k8s) related work you'll need to have
`kubectl`
[installed too](https://kubernetes.io/docs/tasks/tools/install-kubectl/), and
possibly [minikube](https://kubernetes.io/docs/tasks/tools/install-minikube/)
(for running a local k8s cluster).

It may also be useful for when interacting with AWS to have the `aws` command
line tool [installed on your system](https://aws.amazon.com/cli/).

The Control Panel app requires Python 3.6.5+. It has been confirmed to work
with Python 3.8.2.

Install python dependencies with the following command:
```sh
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
pip3 install -r requirements.dev.txt
```

In order to use `direnv` for managing your environment variables, you should
make sure it is [configured for you shell](https://direnv.net/docs/hook.html).
You'll be able to get a copy of folks `.envrc` file from colleagues.

## Local Environment

### <a name="env"></a>Environment variables

The simplest solution is to ask for a copy of a working `.env` or `.envrc` file
from one of the other developers with the envars set for development.

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


### Database

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
postgres=# ALTER USER controlpanel CREATEDB;
```

The last command in the sequence above ensures the `controlpanel` user has the
required privileges to create and delete throw away databases while running the
unit tests.

You must make sure the following environment variables are set:

```sh
export DB_USER=controlpanel
export DB_PASSWORD=password
```

Then you can run migrations:

```sh
python3 manage.py migrate
```


### Compile Sass and Javascript

Before the first run (or after changes to static assets), you need to compile
and collate the static assets.

Static assets are compiled with Node.JS 8.16.0+

```sh
npm install
mkdir static
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


### Run the tests

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

By this step, all the tests should pass. If not, re-check all the steps above
and then ask a colleague for help.


## Third Party Requirements 

Put simply, if you've completed all the steps in the
[new joiners process](https://github.com/ministryofjustice/analytics-platform/wiki/Admin-joiners-and-leavers-process)
then you should be good to go.

In particular, you'll need to make sure you're [set up with Auth0](https://github.com/ministryofjustice/analytics-platform/wiki/Admin-joiners-and-leavers-process#auth0), 
[added to AWS](https://github.com/ministryofjustice/analytics-platform/wiki/Admin-joiners-and-leavers-process#aws)
and have [cluster admin access to Kubernetes](https://github.com/ministryofjustice/analytics-platform/wiki/Admin-joiners-and-leavers-process#kubernetes).

A colleague will need to set you with Auth0, and you should ensure you're using
an account linked to your `@digital.justice.gov.uk` account.

### AWS Configuration

As the docs for AWS (linked above) mention, you'll need to add yourself an AWS
user account linked to your MoJ email address via the
[analytical-platform-iam](https://github.com/ministryofjustice/analytical-platform-iam)
repository. [This pull request](https://github.com/ministryofjustice/analytical-platform-iam/pull/147)
is an example of the sort of thing you'll need to submit (making sure you
modify it to use your own details). Once the PR is approved, you should merge
it yourself. Once this happens a pipeline will process your changes and add
your details to AWS. Remember to follow the remaining instructions in the
README about [first login](https://github.com/ministryofjustice/analytical-platform-iam/#first-login)
for which you'll need to ask someone to create an initial password for you.

Once you're logged you should visit your "security credentials" page (click on
your username in the top right corner) and follow the steps to create an access key for CLI, SDK and API access.

You should also set up a local profile for using MoJ AWS things from your local
machine anyway. Assuming you have the `aws` command installed for your
operating system ([see here](https://aws.amazon.com/cli/)), you can do this
automatically with the following command / dialog. In the example below, I use
the profile name `moj`, but this could be something arbitrary and more
meaningful for you. Then, simply replace the `?????` with your own details. The
`region` and `output format` values should be as shown below.

```
$ aws configure --profile moj
AWS Access Key ID [None]: ?????
AWS Secret Access Key [None]: ?????
Default region name [None]: eu-west-1
Default output format [None]: json
```

Next, you need to assume particular role within AWS in order for the control
panel to have the correct permissions to work with the resources it needs. This
is documented
[here](https://github.com/ministryofjustice/analytical-platform-iam#authenticating),
but the short version is that you need to assume the [restricted-admin@data](https://signin.aws.amazon.com/switchrole?account=mojanalytics&roleName=restricted-admin-data&displayName=restricted-admin@data)
role (clicking on the link, if you're signed into your AWS dashboard, should do
this for you). Once you've assumed this role you need to request temporary
credentials for working with AWS under this role. To do this type the following
command and read the resulting JSON payload:

```
aws sts assume-role --role-arn "arn:aws:iam::593291632749:role/restricted-admin-data" --role-session-name data-session
```

Finally, you need to set the following environment variables, based upon the
values in the returned JSON payload:

```
export AWS_ACCESS_KEY_ID=ASIAX........
export AWS_SECRET_ACCESS_KEY=0vwDrU5..........
export AWS_SESSION_TOKEN="FQoGZXIvYXdzEHQaDHBH......."
```

The last step is to check it worked with the following command (which will
return a JSON payload containing session details):

```
aws sts get-caller-identity
```

If you see an error, ask a colleague!

**You probably notice that the session expires after an hour. If you're getting
AWS errors, ensure you've not timed out.**

### Kubernetes Configuration

For Kubernetes, simply follow the instructions (linked above) for the `dev`
cluster or set up a local cluster as follows:

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

#### Helm

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

## Create superuser (on first run only)

This isn't strictly required, so feel free to skip this step.

```sh
python3 manage.py createsuperuser
```

Your `Username` needs to be your GitHub username.
Your `Auth0 id` needs to be the number associated with you in auth0.com and
labelled `user_id` (not working for me yet).

### Run the app

In order to run the app you'll need various permissions set up for you in the
wider infrastructure of the project.

You can run the app with the Django development server with
```sh
python3 manage.py runserver
```
Or with Gunicorn WSGI server:
```sh
gunicorn -b 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker -w 4 controlpanel.asgi:application
```
Go to http://localhost:8000/, sign in via Auth0 and marvel at your locally
runing control panel.
