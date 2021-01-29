# Running with Docker

The advantage of using docker-compose is that it is configured to run several services that the Control Panel relies on, such as the PostgreSQL database and Redis. It initializes these ready for local development purposes.

## Build

To build the docker image, use the following command:

```sh
docker build -t controlpanel .
```

Hint: If you get error: `Got permission denied while trying to connect to the Docker daemon socket` then it could well be because you're on linux, for which you need to either use sudo or setup to [Manage Docker as a non-root user](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user)

## .env file

You need to create a `.env` file with the settings to enable it to connect to external services. This section explains how to create one.

Lines in this file are simply of format `KEY=value`.

The full list of settings are documented here: [Environment Variables Reference](environment.md). However you can simply get a lot of these values from the settings we use to run Control Panel on the dev cluster. This will connect your locally running Control Panel to AP's dev Auth0 OIDC API, dev Kubernetes cluster, etc. To do this, for the keys listed below, copy the matching lines from chart-env-config/dev/cpanel.yml (in the [config repo](https://github.com/ministryofjustice/analytics-platform-config) and if you've not done so already, you'll need to [decrypt the files in that repo](https://github.com/ministryofjustice/analytics-platform-ops/tree/master/git-crypt#decrypting-the-secrets)) and just change the format of each line to `KEY=value`. These are the keys you need to copy to get your control panel started:

```shell
# To log in with OIDC
OIDC_*
# To interact with AWS account IAM config
AWS_DATA_ACCOUNT_ID
AWS_COMPUTE_ACCOUNT_ID
```

Unless you're testing the Slack feature, just disable it by adding this line:

```shell
SLACK_API_TOKEN=disabled
```

For more details of environment variable settings, refer to: [Environment Variables Reference](environment.md).

## AWS setup

Control Panel needs AWS credentials to change S3 bucket IAM permissions, according to user requests. When it runs in our k8s cluster it can get temporary creds by making a call to kube2iam, which runs in our cluster. But when you run Control Panel locally you'll need to provide AWS credentials that give access to the 'data' AWS account (also known as 'mojanalytics'). The general plan is to configure an AWS access key for your AWS Landing Account's User, and then use AssumeRole to switch to the 'data' (mojanalytics) account.

You can test what AWS Account is currently configured on your command-line, like this:

```shell
$ pip install boto3
$ python -c "import boto3; print(boto3.client('sts').get_caller_identity()['Arn'])"
arn:aws:sts::593291632749:assumed-role/restricted-admin-data/botocore-session-1590188888
```

As an AP developer, if you don't have a Landing AWS Account user account yet, follow the steps here:

1. [Create your AWS user](https://github.com/ministryofjustice/analytical-platform-iam#user-creation). Make sure you're added to the group that gives you access to the 'restricted-admin' role in the 'data' AWS account.
2. Continue those instructions: 'Approve and apply an IAM change', and 'First login'.
3. [Configure your AWS CLI](https://github.com/ministryofjustice/analytical-platform-iam#aws-cli)
4. [Add the special 'data' profile](https://github.com/ministryofjustice/analytical-platform-iam#aws-cli-using-profile).
5. Test it:

    ```sh
    $ AWS_PROFILE=data
    $ python -c "import boto3; print(boto3.client('sts').get_caller_identity()['Arn'])"
    arn:aws:sts::593291632749:assumed-role/restricted-admin-data/botocore-session-1590188888
    ```

Note: You'll have to remember to enable your 'data' AWS profile before running Control Panel, as you would to use the AWS cli:

```shell
AWS_PROFILE=data
```

With this profile activated, boto3 and awscli (`aws`) commands will access the 'data' AWS Account (by using your Landing Account creds and switching to the 'data' account).

If you find you are getting the wrong AWS credentials, it can be useful to know where boto3 searches for AWS credentials and in what order: [boto3's AWS credential search](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#configuring-credentials).

## kubernetes config setup

You need to have a Kubernetes key at ~/.kube/controlpanel. The dev cluster is fine to use.

To do this:

1. Browse to: <https://kuberos.services.dev.mojanalytics.xyz/>
2. Login with your GitHub creds and Auth0 MFA code for dev
3. Look for the second line, where it says "Save **this file** as ~/.kube/config". Download the file linked at "this file"
4. Move the file to `~/.kube/controlpanel` e.g. `mv ~/Downloads/kubecfg.yaml ~/.kube/controlpanel`

## Run

```shell
docker-compose up
```

If it is started up ok you'll see frontend say this:

```shell
frontend_1     | Django version 3.0.5, using settings 'controlpanel.settings'
frontend_1     | Starting ASGI/Channels version 2.4.0 development server at http://0.0.0.0:8000/
frontend_1     | Quit the server with CONTROL-C.
```

and the database migrations finish with code 0:

```shell
analytics-platform-control-panel_migration_1 exited with code 0
```

You can then view the Control Panel in your browser at <http://localhost:8000/>

To create a superuser able to administer the Control Panel, you need to run the
following command in a separate terminal window:

```shell
docker-compose exec app python3 manage.py createsuperuser
```

### Troubleshooting

#### ERROR: pull access denied for controlpanel, repository does not exist or may require 'docker login': denied: requested access to the resource is denied

You probably missed the step to build the controlpanel docker image - see above.

#### relation "django_session" does not exist

You got unlucky. During startup the app tried to use the database a moment before the migrations were applied. Rerun and it will be fine.

#### Page not found (404) Request URL: 	http://localhost:8000/oidc/authenticate/None

You've not setup the OIDC options in your .env file. See instructions above for fixing your .env. Then restart `docker-compose up` and put the URL in again: `http://localhost:8000`.

#### MFA screen keeps appearing

You can break the loop by going back to: `http://localhost:8000`

#### Callback URL mismatch. The provided redirect_uri is not in the list of allowed callback URLs.

You probably put the wrong URL into your browser to start off with. Make sure it is the one in these docs. Use `localhost` rather than `0.0.0.0`, for example.

You can also check that your callback URL is configured in the Auth0 dashboard. If you're using the 'dev' environment OIDC then go to Auth0 'dev-analytics-moj' tenant: <https://manage.auth0.com/dashboard/eu/dev-analytics-moj/applications>. Find the Application with Client ID matching the `OIDC_CLIENT_ID` in your .env. In its config check the 'Allowed Callback URLs'.

#### NoCredentialsError at /oidc/callback/

This is boto3 saying it can't find any AWS credentials. See instructions above for AWS setup.

#### NoSuchEntityException at /oidc/callback/

"An error occurred (NoSuchEntity) when calling the AttachRolePolicy operation: Policy arn:aws:iam::None:policy/dev-read-user-roles-inline-policies does not exist or is not attachable."

You've not set the AWS_DATA_ACCOUNT_ID setting.

#### ConfigException at /tools/ - Invalid kube-config file. Expected object with name  in /home/controlpanel/.kube/config/contexts list

It can't find your k8s config file - see kubernetes config above.

## Running tests

To run the test suite inside a docker container, use the following command:

```shell
make docker-test
```

# Dockerfile structure

The `Dockerfile` defines a multi-stage build with the following structure:

  1. Create a `base` image, building on Alpine and installing needed OS packages
  2. Download and install Helm
  3. Install Python dependencies
  4. Create a `jsdep` image, based on Node to download Javascript dependencies using `npm`
  5. Copy Javascript dependencies to the `base` image
  6. Collect static files ready to serve

Using a separate `jsdep` image means the final image doesn't need Node.JS
installed.

This structure hopefully makes the best use of the Docker cache, in that more
frequent updates to Javascript and Python dependencies happen later in the
build, and less frequent, more cachable updates to OS packages and Helm are
earlier.
