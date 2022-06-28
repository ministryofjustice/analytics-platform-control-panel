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

Control Panel is a Django project made up of four parts:

1. Major features for interacting with infrastructure for creating users, apps, tools & managing permissions in the
   Analytical Platform Kubernetes cluster, Auth0 and AWS IAM are under /controlpanel/api. 
   
2. A basic structure of REST APIs for allowing external systems to view the resources managed through the app.
   
3. A frontend web application allowing administration of a user's apps, data
   sources and tools in the Analytical Platform.
   
4. A simple worker for running some time-consuming background tasks 
   
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

## Deployment EKS Infrastructure

Currently this is NOT automated, but there is a ticket in the backlog to make
things work in a similar fashion to how it does on the old infrastructure but
via GitHub actions rather than Concourse.

The modus operandi is simple:

* In our [flux repository](https://github.com/moj-analytical-services/analytical-platform-flux), you'll find two subdirectories: `development` and `production`. Each one refers to the configuration of the named EKS instance. Inside each of these is a further `apps` directory.
* In these directories are further sub-directories for the various aspects of our infrastructure. Obviously, the subdirectory we're interested in is called `apps/cpanel`.
* Inside the `cpanel` directory is a file called `cpanel.yaml`. This is the file that needs changing.
* Find the build tag for the docker image of the version of the Control Panel that you want to deploy, on our Amazon ECR service (where builds are automatically pushed from GitHub).
* Update the `spec.values.image.tag` value with the build tag of the required image, save, create a new branch, push the branch to GitHub and then generate a new PR.
* Once the PR is merged, flux will ensure the instances of the Control Panel are updated to the specified image.

That's it..!


## Other useful documentation

* [Some semi-common errors](./doc/errors.md)
* [Helm charts repo](https://github.com/ministryofjustice/analytics-platform-helm-charts)
