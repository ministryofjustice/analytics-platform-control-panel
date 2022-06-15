# Analytical Platform Control Panel

The Control Panel is a Django project made up of two parts:

1. A REST API for creating users, apps, tools & managing permissions in the
   Analytical Platform Kubernetes cluster, Auth0 and AWS IAM.

2. A frontend web application allowing administration of a user's apps, data
   sources and tools in the Analytical Platform.


## Quickstart

You can set up a local instance of Control Panel via [Docker](doc/docker.md) or by [running directly on your machine](doc/running.md).
Both guides recently underwent substantial revisions to make them compatible with our new EKS cluster; please discuss any issues you come across with the team and open a PR to revise the setup documentation.


## Deployment


Currently deployment to our new EKS cluster is NOT automated, but there is a ticket in the backlog to make things work in a similar fashion to how it does on the old infrastructure but via GitHub actions rather than Concourse.

The modus operandi is simple:

* In our [flux repository](https://github.com/moj-analytical-services/analytical-platform-flux), you'll find two subdirectories: `development` and `production`. Each one refers to the configuration of the named EKS instance. Inside each of these is a further `apps` directory.
* In these directories are further sub-directories for the various aspects of our infrastructure. Obviously, the subdirectory we're interested in is called `apps/cpanel`.
* Inside the `cpanel` directory is a file called `cpanel.yaml`. This is the file that needs changing.
* Find the build tag for the docker image of the version of the control panel that you want to deploy, on our Amazon ECR service (where builds are automatically pushed from GitHub).
* Update the `spec.values.image.tag` value with the build tag of the required image, save, create a new branch, push the branch to GitHub and then generate a new PR.
* Once the PR is merged, flux will ensure the instances of the control panel are updated to the specified image.

That's it..!


## Documentation

Our documentation for getting started with this repo can be found in the following files in the `docs` folder:
* [Running control panel locally](./doc/running.md)
* [Running control panel with docker](./doc/docker.md)
* [Control Panel environment variables](./doc/environment.md)
* [The control panel frontend](./doc/frontend.md)
* [The control panel data model](./doc/data_structure.md)
* [Some semi-common errors](./doc/errors.md)
Note that some of these pages have not been updated following the switch from the old KOPS cluster to the new EKS one, so may contain outdated information.

For further details about the Analytical Platform, see our [Technical Documentation](https://silver-dollop-30c6a355.pages.github.io) site.
