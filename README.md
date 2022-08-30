# Analytical Platform Control Panel

The Control Panel is a management tool which provides the following features to our main stakeholders, the Ministry of Justice's Data Analysts and Data Scientists: 

- Allow them to access important datasets from across the MoJ easily and securely
- Allow them to manage their own datasets easily and securely
- Allow them to explore the data by using our online tooling environment 
- Allow them to deploy customised dashboards on our hosting platform

For administrators, Control Panel offers
- User management 
- Permission management on datasets
- Application management

Control Panel interacts heavily with our underlying infrastructure, such as our Kubernetes clusters and S3 buckets (AWS).
It also has tight dependencies on the policies and strategies about how we manage our data lake and our infrastructure.

## Tech documents

Control Panel is a Django project made up of three parts:

1. A REST API for creating users, apps, tools & managing permissions in the Analytical Platform Kubernetes cluster, Auth0 and AWS IAM, and to allow external systems to view the created resources. This can be found under `/controlpanel/api`.
   
2. A frontend web application allowing administration of a user's apps, data
   sources and tools in the Analytical Platform.
   
3. A simple worker for running some time-consuming background tasks such as deploying a tool (e.g. RStudio or JupyterLab) on a cluster, restarting the instance of a tool, and resetting the home directory of a user's tooling environment.
   
More information is available through the following links:

* [Control Panel architecture](./doc/architecture.md)
* [Control Panel data model](./doc/data_structure.md)
* [Control Panel frontend](./doc/frontend.md)

## Quickstart

To work with Control Panel yourself, we currently recommend setting up a local instance of the project.
To do so, see our getting started guide in [`doc/running.md`](./doc/running.md).

Formerly, we could also run a local instance of Control Panel via Docker but we have decided to pause the work needed to update this process (which was necessary after migrating to our new EKS cluster) in favour of an improved solution via LocalStack.
See tickets [ANPL-839](https://dsdmoj.atlassian.net/browse/ANPL-839) and [ANPL-858](https://dsdmoj.atlassian.net/browse/ANPL-858) for the current status of this work.

For better understanding of the settings and environment variables used while running Control Panel, please check the [Control Panel settings and environment variables](./doc/environment.md) file.

## Other useful documentation

* [Deploy a new Control Panel release](https://silver-dollop-30c6a355.pages.github.io/documentation/40-infrastructure/20-common-tasks/Deploy-new-control-panel-release.html#deploy-a-new-control-panel-release)
* [Authentication flows](./doc/auth_flows.md)
* [Some semi-common errors](./doc/errors.md)
* [Helm charts repo](https://github.com/ministryofjustice/analytics-platform-helm-charts)
