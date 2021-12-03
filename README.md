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

Commits to the protected `master` branch will trigger a [Concourse CI pipeline](https://concourse.services.dev.mojanalytics.xyz/teams/admin/pipelines/cpanel-api) which will deploy the changes to our `dev` environment.
Versioned Github releases will trigger [another pipeline](https://concourse.services.alpha.mojanalytics.xyz/teams/admin/pipelines/cpanel-api) and deploy to our `alpha` environment.


## Documentation

* [Running control panel locally](./doc/running.md)
* [Running control panel with docker](./doc/docker.md)
* [Control Panel environment variables](./doc/environment.md)
* [The control panel frontend](./doc/frontend.md)
* [The control panel data model](./doc/data_structure.md)
* [Some semi-common errors](./doc/errors.md)
