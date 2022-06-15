# KIND SPIKE BRANCH

For details check [here](./current_status_of_spike.md)


[![Docker Repository on Quay](https://quay.io/repository/mojanalytics/control-panel/status "Docker Repository on Quay")](https://quay.io/repository/mojanalytics/control-panel)

# Analytical Platform Control Panel

The Control Panel is a Django project made up of two parts:

1. A REST API for creating users, apps, tools & managing permissions in the
   Analytical Platform Kubernetes cluster, Auth0 and AWS IAM.

2. A frontend web application allowing administration of a user's apps, data
   sources and tools in the Analytical Platform.


## Quickstart

See [Running with Docker](doc/docker.md), or [Running directly on your
machine](doc/running.md).


## Deployment


### Old (pre-EKS) Infrastructure

Commits to the protected `main` branch will trigger a [Concourse CI pipeline](https://concourse.services.dev.mojanalytics.xyz/teams/admin/pipelines/cpanel-api) which will deploy the changes to our `dev` environment.

To deploy work branches for testing purposes on the old `dev` environment see [the instructions here](https://ministryofjustice.github.io/ap-tech-docs/documentation/50-systems/control-panel/Deploy-Development-Instance-of-Control-Panel.html).

Versioned Github releases will trigger [another pipeline](https://concourse.services.alpha.mojanalytics.xyz/teams/admin/pipelines/cpanel-api) and deploy to our `alpha` environment.

### New (EKS) Infrastructure

Currently this is NOT automated, but there is a ticket in the backlog to make
things work in a similar fashion to how it does on the old infrastructure but
via GitHub actions rather than Concourse.

The modus operandi is simple:

* In our [flux repository](https://github.com/moj-analytical-services/analytical-platform-flux), you'll find two subdirectories: `development` and `production`. Each one refers to the configuration of the named EKS instance. Inside each of these is a further `apps` directory.
* In these directories are further sub-directories for the various aspects of our infrastructure. Obviously, the subdirectory we're interested in is called `apps/cpanel`.
* Inside the `cpanel` directory is a file called `cpanel.yaml`. This is the file that needs changing.
* Find the build tag for the docker image of the version of the control panel that you want to deploy, on our Amazon ECR service (where builds are automatically pushed from GitHub).
* Update the `spec.values.image.tag` value with the build tag of the required image, save, create a new branch, push the branch to GitHub and then generate a new PR.
* Once the PR is merged, flux will ensure the instances of the control panel are updated to the specified image.

That's it..!


## Documentation

* [Running control panel locally](./doc/running.md)
* [Running control panel with docker](./doc/docker.md)
* [Control Panel environment variables](./doc/environment.md)
* [The control panel frontend](./doc/frontend.md)
* [The control panel data model](./doc/data_structure.md)
* [Some semi-common errors](./doc/errors.md)
