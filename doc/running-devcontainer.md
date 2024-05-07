# Running on your machine via a Dev Container

This guide describes how to run Control Panel locally with a Dev Container. This requires Docker and an IDE that can work with Dev Containers (Visual Studio Code advised). This will setup the majority of things for you, including your database, Redis, and AWS credentials.

## Prerequisites

Visual Studio Code with the Dev Container [extension](https://www.google.com/search?q=dev+container+extension&sourceid=chrome&ie=UTF-8) and Docker Desktop are required. You will also need to be able to access AWS. The Python Dev Container [extension](https://code.visualstudio.com/docs/languages/python) is recommended.

### Git
In order to get git to recognise your SSH key while working in the Dev Container:
- Add your SSH keys to your ssh agent by running `ssh-add <.ssh-location>/<ssh-key-filename-without-extension>` e.g. `ssh-add ~/.ssh/id_ed25519`
- Set your signing key in your `.gitconfig` file to the contents of your public key by running `git config --global user.signingkey key::<your-key-here>`

### Environment Variables

Download a copy of a working `.env` file from the Analytical Platform Vault in [1Password](https://ministryofjustice.1password.eu/vaults/skgdudwgk3ojqiwigoxrmpngle/tags/fioo45n5zohrdsf6mkdikito4d/osqkxdboemvpsgl4g2zt3kyuia). Copy the contents into a `.env` file in the root directory of the project.

If you have an existing local `.env` file, there are slight differences. Notably `AWS_CONFIG_FILE` needs to be added and `AWS_PROFILE` and `HELM_REPOSITORY_CACHE` need changing to reference dev-container directories.

See [Control Panel settings and environment variables](environment.md) for details of other settings and environment variables.

## 1. Building the Dev Container
You will need Docker Desktop along with Visual Studio Code and the Dev Container [extension](https://www.google.com/search?q=dev+container+extension&sourceid=chrome&ie=UTF-8) installed to build the container.

To build the Dev Container, ensure Docker Desktop is running, then open the Analytical Platform Control Panel project in Visual Studio Code. Open the Command Pallete by hitting `Cmd + Shift + p` and search then select `Dev Containers: Reopen in container` to build the Dev Container.

If you are using a workspace with multiple applications, search for `Dev Containers: Open folder in Container…` instead, then select the Control Panel folder. Once the Dev Container has finished building, it should install all the required Python and npm dependencies, as well as run the migrations and install the helm charts.

As part of the install, it will also try and create your AWS and Kubernetes config. Be sure to keep an eye on your terminal and navigate to the AWS SSO site when prompted. Once this has finished, select yes on the second prompt then your Dev Container will have finished building.

## 2. Local Environment

### Running the Message broker

The Control Panel uses a message queue to run some tasks. For local development, Redis
is recommended as the message broker rather than SQS (which is used in the development
and production environments). To run the message broker, use the following make command

```sh
make celery-sso
```

This will need to run in a separate terminal instance.

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


## Run the Application

**Assumption**:
- You have completed your local env setup by following the above sections.
- we use aws with sso login, the name of profile for our aws dev account is `analytical-platform-development:AdministratorAccess`

### Check Kubernetes current context

Please check the current context and make sure it is pointing to the `dev` cluster. This should be done for you automatically. You can manually set the cluster by using:

```sh
kubectl config use-context <dev_cluster_name>    # get name from your ~/.kube/config file
```

### Create superuser (on first run only)

This isn't strictly required, so feel free to skip this step.

```sh
python3 manage.py createsuperuser
```

Your `Username` needs to be your GitHub username.
Your `Auth0 id` needs to be the number associated with you in auth0.com and
labelled `user_id` (not working for me yet).


### Run the frontend of the Application

You can run the Application, in a separate terminal, with the Django development server by running:

```sh
make serve-sso
```

Then navigate to `localhost:8000`

On first run of the application, after logging in, you will likely run into a HelmError with the message `UPGRADE FAILED: failed to replace object: Job.batch "config-git-<user>-jupyter" is invalid`. See the troubleshooting section for a workaround to this issue.

### Visual Studio Code - Debugger Setup

You can configure Visual Studio Code to run the Django server and Celery together, with AWS credentials for the
analytical-platform-development environment sourced. You can configure this and other debugger
configurations yourself following the [Visual Studio Code documentation](https://code.visualstudio.com/docs/editor/debugging)
or use the included example files to get started immediately by following these steps:

- In the project root create a `.vscode` folder if it does not already exist.
- Copy the [`launch.json.example`](./launch.json.example) and [`tasks.json.example`](./tasks.json.example)
files to the `.vscode` directory, removing the `.example` suffix.
- In the Visual Studio Code sidebar select the "Run and debug" icon, choose the `Runserver/Celery`
configuration and click the start button or use the F5 shortcut. Note: if you are not already logged
in with `aws-sso` check the terminal output for a link to do so.

The Django server and Celery should now both be running, and you can set breakpoints to help debug
your code. [See the Visual Studio Code documentation for more details about using the debugger.](https://code.visualstudio.com/docs/editor/debugging#_breakpoints)

### Run the worker of the app
Open another terminal to run the following line

```sh
python manage.py runworker background_tasks
```

Go to `http://localhost:8000/`, sign in via GitHub through Auth0 and marvel at your locally
running control panel.

Note: if you use [aws-vault](https://github.com/99designs/aws-vault) to manage your AWS credentials, during the running process of the application, you may encounter a popup window for asking you to provide key-chain password from time to time, which is normal.

### Loading tools

When you load up your local Control Panel for the first time, there will be no tools available on the Tools page.
To pre-populate the database, run the following management command:

```sh
python manage.py loaddevtools controlpanel/api/fixtures_dev/tools.yaml
```
You can also use this command to load up your own tools fixture files if you want to add more tools to the database.

Note: that you will need to have the RStudio and JupyterLab Auth0 environment variables present in your `.env` file in order for the missing values in the `tools.yaml` fixture file to be filled in.
Check that you have `<TOOL>_AUTH_CLIENT_DOMAIN`, `<TOOL>_AUTH_CLIENT_ID` and `<TOOL>_AUTH_CLIENT_SECRET` for both RStudio and JupyterLab before running `loaddevtools`.

### Important notes

Even though your instance of Control Panel is running locally, it will still interact with the remote AWS dev account and development Kubernetes cluster.
The dev account is also used by our development cloud environment, so take care when interacting with our AWS resources directly.

## Development Practices

### pre-commit

`pre-commit` is a package manager for git hooks that we use during local development.

Current checks are:-
- requirements.txt library sort and check
- yaml file check
- end-of-file must have white line
- trailing white spaces check
- `black` library (formats Python code)
- `isort` library (standardises the order of Python imports)
- `flake8` library (formats Python code and also improves code style)

To override the above for whatever reason (maybe you don't have a ticket number and because you are working on hotfix) you can use the following command.

`PRE_COMMIT_ALLOW_NO_CONFIG=1 git push ...`

### Troubleshooting

When first logging into the control panel, you may find that you run into an error regarding not being able to write to the helm charts. A workaround for this is to go to `/workspaces/analytics-platform-control-panel/controlpanel/api/models/user.py` and comment out lines `145-146` and `151-154`. Once logged into the control panel, comment the lines back in.
