# Running directly on your machine

---
:construction: _This guide has recently undergone some major changes in order to work with the new cluster. It should include all the changes needed to get from a fresh system to having a local instance of Control Panel, but be aware that the developers who checked the system had some things set up already. If problems arise, please open a PR to revise this documentation._

---

This guide describes how to run Control Panel locally without Docker, and so that it can interact with the following remote AWS resources:
 - AWS Data account
 - AWS Dev account
 - AWS EKS cluster on Dev account

There are essentially three aspects to getting the Control Panel in a state for
development on your local machine:

1. Ensuring you have all the required dependencies installed, and these are all
   correctly configured.
2. Acquiring the credentials and permissions needed for the various third-party
   aspects of the project (AWS, Auth0, k8s).
3. Getting hold of the source code for the project and creating a local
   environment in which to be able to work.


The third party services used by the application are labelled as either `dev`
(for use as part of the development / testing process) and `alpha` (which is
what our users use). Obviously, you should avoid using the `alpha` labelled
versions of the services.

## 1. Required Dependencies

The Control Panel app requires Python 3.6.5+. It has been confirmed to work
with Python 3.8.12.

Install python dependencies with the following command:
```sh
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
pip3 install -r requirements.dev.txt
pip3 uninstall python-dotenv    # see ANPL-823
```

In addition, you must have:

* [Redis](https://redis.io/) (confirmed to work with v7.0.0)
* [PostgreSQL](https://www.postgresql.org/) (v14.3)
* [npm](https://www.npmjs.com/)
* [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-macos/#install-with-homebrew-on-macos) (v1.23.4)
* [helm](https://helm.sh/docs/intro/install/) (v3.6.3, v3.8.0)
* [direnv](https://direnv.net/)

We recommend installing these tools via Homebrew.

You may want to set Postgres and Redis to start up automatically, in which case run
```
brew services start postgres
brew services start redis
```
and you can check their status with
```
brew services list
```
Otherwise, make sure you have started both manually before attempting to run Control Panel locally.

To interact with AWS, you should also set up the [`aws` command
line interface](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

In order to use `direnv` for managing your environment variables, you should
make sure it is [configured for your shell](https://direnv.net/docs/hook.html).


## 2. Third Party Requirements

Put simply, if you've completed all the steps in the
[Technical Setup](https://silver-dollop-30c6a355.pages.github.io/documentation/10-team-practices/new-joiners.html#technical-setup) section of our New Joiners' Guide
then you should be good to go.

In particular, you'll need to make sure you're [set up with Auth0](https://silver-dollop-30c6a355.pages.github.io/documentation/10-team-practices/new-joiners.html#auth0),
[added to AWS](https://silver-dollop-30c6a355.pages.github.io/documentation/10-team-practices/new-joiners.html#aws)
and have [cluster admin access to Kubernetes](https://silver-dollop-30c6a355.pages.github.io/documentation/10-team-practices/new-joiners.html#kubernetes).


### AWS Configuration

In order to run the app you'll need various permissions set up for you in the
wider infrastructure of the project, mainly for AWS platform. 

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

`aws-vault` is recommended to manage different AWS accounts

See [here for more information](https://github.com/ministryofjustice/analytical-platform-iam/blob/main/documentation/AWS-CLI.md)
for details of information about how to setup configuration and how to use `aws-vault`.

### Kubernetes Configuration

For Kubernetes, simply follow the instructions (linked above) for the `dev`
cluster.

Make sure you have the correct kubernetes context set:
```sh
kubectl config use-context <dev-cluster-name>   # cluster name as set in ~/.kube/config
```

You can check things are working with the following command, which will return
information about the k8s master and KubeDNS:

```sh
kubectl cluster-info
```
The token for accessing the cluser will expire periodically.
To refresh the token automatically, the following lines can be added into your ~/.kube/config:

### Environment variables

For easy switching between Kubernetes contexts (to connect to dev/prod clusters), you may find it helpful to use [`kubie`](https://blog.sbstp.ca/introducing-kubie/).

### Helm

You will need to initialise Helm:

```sh
helm init
```

Tell Helm to use the Analytical Platform chart repository:

```sh
helm repo add mojanalytics http://moj-analytics-helm-repo.s3-website-eu-west-1.amazonaws.com
helm repo update
```

## 3. Local Environment

### Environment variables

The simplest solution is to download the copy of the working `.env` or `.envrc` file from [LastPass](https://silver-dollop-30c6a355.pages.github.io/documentation/10-team-practices/new-joiners.html#lastpass).
Check each value whether it is relevant to your local env.

Check that the environment variable `DB_HOST` is set to `localhost` - this is a recent revision to the `.env` file and may not be captured in your copy.

See [Control Panel settings and environment variables](environment.md) for details of other settings and environment variables.

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
./node_modules/.bin/sass --load-path=node_modules/ --style=compressed controlpanel/frontend/static/app.scss:static/app.css
```

Then run collectstatic:
```sh
python3 manage.py collectstatic
```

### Run the tests

Run the tests using `pytest`:

```sh
DJANGO_SETTINGS_MODULE=controlpanel.settings.test pytest
```

**NOTE** Setting `DJANGO_SETTINGS_MODULE` is important or otherwise you
may accidentally run the tests with the `development` settings with
unpredictable results.

By this step, all the tests should pass. If not, re-check all the steps above
and then ask a colleague for help.


## Run the app

**Assumption**: You have completed your local env setup by following the above sections.

### Local AWS profile setup (on first run only)
This app needs to interact with multiple AWS accounts in order to support the users' needs.
The AWS resources like IAM, s3 buckets are under our data account and will be managed by 
app through [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html). In order to make sure the boto3 can obtain the right profile for local env.
The following steps will show how to create it.

Assume that the name of profile for our aws data account is ```admin-data```

#### Add the AWS credential into .aws/credentials
it should look like below 
```
[admin-data]
aws_access_key_id = <your aws_access_key_id>
aws_secret_access_key = <your aws_secret_access_key>

```
As you need your AWS access keys above, you can find them out via the following link if you use aws-vault to manage your keys
https://github.com/99designs/aws-vault/blob/master/USAGE.md#keychain

Once the aws-vault is added, you can choose to show the value of the keys.

#### Add the AWS assume role or other settings into .aws/config

```
[profile admin-data]
role_arn=arn:aws:iam::<data account id>:role/restricted-admin
source_profile=default
```
### Check Kubernetes current context

Please check the current context and make sure it is pointing to the `dev` cluster

```sh
kubectl config use-context <dev_cluster_name>    # get name from your ~/.kube/config file
```

### Check the environment file

#### General checks

Check whether you have the following 2 in the env file and make sure they are correct
- ```HELM_REPOSITORY_CACHE```:  the directory for helm repo cache folder.


if you install helm chart by default settings, please make sure to setup the ```HELM_REPOSITORY_CACHE```
the default value is ```/tmp/helm/cache/repository```

```
export HELM_REPOSITORY_CACHE="/Users/<user name>/Library/Caches/helm/repository"
```
if you are not sure, can use the following command to find it out

```shell
helm env
```
Note that even if the variable is set correctly in the output of the above command, you still need to export it as an environment variable.

#### AWS credential setting for single AWS role
If you want to run the control panel app to manage AWS resources under single role, you can use
following environment variable to define the profile you want to use
- ```AWS_PROFILE```: The profile which will be used for ```boto3``` auth
export AWS_PROFILE = "admin-data"
- Make sure there is NO other AWS boto3 environment variables defined. 

#### AWS credential setting for multiple AWS roles
If you want to run the app to manage the AWS resources cross different AWS accounts by assuming 
different roles, then
- Check whether following 2 more environment variables have been setup in the env file or not
  - `AWS_DATA_ACCOUNT_ROLE`: The role_arn of admin-data account
  - `AWS_DEV_ACCOUNT_ROLE` : The role_arn of admin-dev account
  
if you are not sure what the value of role_arn of those two accounts is, you can find them out by
  checking the aws config file. 

More detail about the settings for mult-account is [here](architecture.md) (last section)
- Make sure other AWS boto3 settings e.g. ```AWS_PROFILE``` are NOT defined in your env, otherwise the app will
end up with root level session under a role, and you may get exception like `couldn't assume this role`

### Create superuser (on first run only)

This isn't strictly required, so feel free to skip this step.

```sh
python3 manage.py createsuperuser
```

Your `Username` needs to be your GitHub username.
Your `Auth0 id` needs to be the number associated with you in auth0.com and
labelled `user_id` (not working for me yet).


### Run the frontend of the app

You can run the app with the Django development server with

```sh
python3 manage.py runserver
```
Or with Gunicorn WSGI server:

```sh
gunicorn -b 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker -w 4 controlpanel.asgi:application
```

### Run the worker of the app
Open another terminal to run the following line

```sh
python manage.py runworker background_tasks
```

Go to http://localhost:8000/, sign in via Auth0 and marvel at your locally
running control panel.

NOTES: if you use aws-vault to manage your AWS credentials, during the running process of the app,
you may encounter a popup window for asking you to provide key-chain password from time to time, 
which is normal.

### Loading tools

When you load up your local Control Panel for the first time, there will be no tools available on the Tools page.
To pre-populate the database, run the following management command:
```
python manage.py loaddevtools controlpanel/api/fixtures_dev/tools.yaml
```
You can also use this command to load up your own tools fixture files if you want to add more tools to the database.

Note that you will need to have the RStudio and JupyterLab Auth0 environment variables present in your `.env` file in order for the missing values in the `tools.yaml` fixture file to be filled in.
Check that you have `<TOOL>_AUTH_CLIENT_DOMAIN`, `<TOOL>_AUTH_CLIENT_ID` and `<TOOL>_AUTH_CLIENT_SECRET` for both RStudio and JupyterLab before running `loaddevtools`.

### Important notes

Even though your instance of Control Panel is running locally, it will still interact with the remote AWS data account and development Kubernetes cluster.
The data account is also used by our production environment, so take care when interacting with our AWS resources directly.
