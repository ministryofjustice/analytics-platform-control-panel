[![Docker Repository on Quay](https://quay.io/repository/mojanalytics/control-panel/status "Docker Repository on Quay")](https://quay.io/repository/mojanalytics/control-panel)

# Analytical Platform Control Panel

The Control Panel is a management tool which provides the following features to our main stakeholders, data analysts 
and data scientists: 

- Allow them to access important datasets from across MoJ easily and securely
- Allow them to manage their own datasets easily and securely
- Allow them to explore the data by using our online tooling environment 
- Allow them to deploy their app on our hosting platform easily

For administrators, Control Panel can offer
- User management 
- Permission management on datasets
- Application management

As the nature of this app, Control Panel interacts heavily with our underlying infrastructure, which is mainly AWS services and clusters.
It also has tight dependencies on the policies and strategies about how we would like to manage our data lake and our infrastructure.

## Tech documents

Control Panel is a Django project made up of three parts:

1. A REST API for creating users, apps, tools & managing permissions in the Analytical Platform Kubernetes cluster, Auth0 and AWS IAM, and to allow external systems to view the created resources. This can be found under `/controlpanel/api`.
   
2. A frontend web application allowing administration of a user's apps, data
   sources and tools in the Analytical Platform.
   
3. A simple worker for running some time-consuming background tasks such as deploying a tooling (e.g. RStudio or Jupyter Lab) on a cluster, restarting the instance of a tool, and resetting the home directory of a user's whole tooling environment.
   
More information is available through the following links:

* [Control Panel architecture](./doc/architecture.md)
* [Control Panel data model](./doc/data_structure.md)
* [Control Panel frontend](./doc/frontend.md)

## Quickstart

Unfortunately, there is no real quickstart for this Control Panel at this stage. 
In order to be able to work on the app locally, there are two options:

- Interact with remote infrastructure (AWS platform) for dev environment 
  
  Under this option, first you will need to obtain the permissions required to access
  the different resources on our infrastructure e.g., AWS. Then, see [Running with Docker](doc/docker.md), 
  or [Running directly on your machine](doc/running.md).

- Interact with local infrastructure through LocalStack **(currently under development)**

For better understanding of the environment variables used in this app, please check the [Control Panel environment variables](./doc/environment.md) file.

## Other useful documentation

* [Deploy a new Control Panel release](https://silver-dollop-30c6a355.pages.github.io/documentation/40-infrastructure/20-common-tasks/Deploy-new-control-panel-release.html#deploy-a-new-control-panel-release)
* [Authentication flows](./doc/auth_flows.md)
* [Some semi-common errors](./doc/errors.md)
* [Helm charts repo](https://github.com/ministryofjustice/analytics-platform-helm-charts)
