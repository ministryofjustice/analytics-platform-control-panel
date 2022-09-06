# Architecture

This document shows the key design and implementation of Control Panel, but it does not go down into the deepest level of detail.
Once you have familiarised yourself with the application's architecture using this document, we recommend delving into the code and our [technical documentation site](https://silver-dollop-30c6a355.pages.github.io/documentation/50-systems/control-panel/#control-panel) for further details.

## System overview
![System Overview](./images/system_overview.png "The system overview of the app")

The system diagram above shows the many external tools, services and platforms that the Control Panel interacts with.
This partially explains that the complicated aspects of this app do not arise from the users' requirements, but rather the integration with different external systems.

A few points of particular note:
- Users authenticate to the Control Panel via GitHub through Auth0.
- The main infrastructure that the app communicates with is AWS, including IAM, SSM, Secrets Manager, and EKS clusters.
- Each interaction with an external system requires an authentication + authorisation process, especially for AWS. 
Control Panel needs access to several different AWS accounts which are used to manage different resources. This separation improves the security and organisation of our resources.

## Authentication

The authentication between our end users and the apps including Control Panel, tooling 
and AWS console is managed through Auth0 by using GitHub as an external Identity Provider.

Auth0 is a platform which sits between our applications and our sources of users, 
which adds a level of abstraction so the applications are isolated from any changes to and 
idiosyncrasies of each source's implementation.

More detail information can be read from this link
[Auth0 introduction](https://auth0.com/docs/)


![Authentication Overview](./images/authentication.png "The authentications of the app")

The detailed authentication flow for each login from above diagram is available [here](./doc/auth_flows.md)

## Code structure overview
As we can see above system overview diagram, every external system and service that the Control Panel app interacts with needs 
an authentication process. The majority of them use client-credentials (client_id and client_secret) for 
machine to machine authentication. The slightly complicated part is the interactions with AWS 
services and clusters, which is shown in the following diagram. 

![Code structure](./images/code_structure.png "The code structure of the app")

In order to manage our AWS infrastructure under different AWS accounts, 
our Control Panel connects to an account which can assume
different roles which have the necessary permissions to access resources in different accounts. More information about this approach can be found in [the AWS docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_cross-account-with-roles.html).

The high level implementation diagram is below 

![auth aws for multi accounts](./images/aws_auth_multi_roles_design_diagram.png "The design diagram for multi aws accounts")


The mapping between which role the control panel should pick up to create the AWS resource for particular
entity on the app is achieved by using the following convention:
- configuration in the settings.yaml
  2 level of structure, the first level is the role category which normally represents the entity class. 
  The second level represents the AWS service API which maps the class in aws.py. Each level can have a default role

```yaml
AWS_ROLES_MAP:
  DEFAULT: AWS_DATA_ACCOUNT_ROLE
  USER:
    DEFAULT: AWS_DATA_ACCOUNT_ROLE
    AWSROLE: AWS_DATA_ACCOUNT_ROLE
    AWSBUCKET: AWS_DATA_ACCOUNT_ROLE
    AWSPOLICY: AWS_DATA_ACCOUNT_ROLE
    AWSSECRETMANAGER: AWS_DATA_ACCOUNT_ROLE
  APP:
    DEFAULT: AWS_APP_ACCOUNT_ROLE
    AWSROLE: AWS_APP_ACCOUNT_ROLE
    AWSBUCKET: AWS_DATA_ACCOUNT_ROLE
    AWSPOLICY: AWS_DATA_ACCOUNT_ROLE
    AWSPARAMETERSTORE: AWS_APP_ACCOUNT_ROLE
    AWSSECRETMANAGER: AWS_APP_ACCOUNT_ROLE

```

- The above one is most detail level you can configure under current implementation. It can be simplied as following one
  if all the AWS resources are managed under one account, 
```yaml
AWS_ROLES_MAP:
  DEFAULT: AWS_DATA_ACCOUNT_ROLE
```  
  or simplied as below if users' resources and apps' resources are managed under separated accounts
```yaml
AWS_ROLES_MAP:
  DEFAULT: AWS_DATA_ACCOUNT_ROLE
  USER:
    DEFAULT: AWS_DATA_ACCOUNT_ROLE
  APP:
    DEFAULT: AWS_APP_ACCOUNT_ROLE
```
- The logic for searching the roles through the configuration: it will try to search from lowest level based on the 
  category name and aws service name, if couldn't find, then go up to the category level, if found then use the default
  role for this category, if even category name cannot be found, then the root default role will be applied.
  
- Right now the resource like IAM roles, secrets can be managed under different accounts except the S3bucket as 
 there are some dependencies in the current implementation and the infrastructure both. 