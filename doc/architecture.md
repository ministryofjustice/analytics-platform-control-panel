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


The mapping between the AWS resource that Control Panel manages and the role that it should assume in order to do so is set via the mapping below, which is stored in `settings.yaml`.

There are two levels of structure:
- The first level is the role category which normally represents the entity class.
- The second level represents the AWS service API which maps to the class in `aws.py`. Each level can have a default role.

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

The above mapping is most detailed level you can configure under current implementation. It can be simplified to following if all the AWS resources are managed under one account:
```yaml
AWS_ROLES_MAP:
  DEFAULT: AWS_DATA_ACCOUNT_ROLE
```  
or reduced to the following if users' resources and apps' resources are managed under separate accounts:
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
  
- Right now most resources like IAM roles and secrets can be managed under different accounts. 
  S3 buckets are an exception as there are some dependencies in both the current implementation 
  and the infrastructure.
  
- The feature of supporting the multi AWS accounts was required by the app migration, since we changed
  cluster to Cloud-Platoform team, the feature is not required any more but we are not going to revert
  the code back as the current code support single account too
  
## Message Broker and Queue
The Control panel is under the process of refactoring how we manage/trigger/perform the tasks which are related to
external third party of tools, service and infrastructure including AWS and cluster etc,.
Although right now those tasks are mainly application and user related, potentially it can be
extended to other type of resources the future. 

We introduce the message broker and queue as the key role during this process, 

The main reasons for introduce the MB and MQ:
- Make the sequences of task more controllable and not affect each other, more robust 
- Outsource or offload the heavy task (e.g. ip_range lookup table change)
- Make the parts related infrastructure side easier to be maintained or be replaced
  better visibility for background tasks
  
Main tech stack
- Use AWS SQS as message broker
- Use celery for workers
- User boto3 to send message but following the message protocol of celery for 
  decoupling sender from particular mq client

## RESTFul APIs

Two ways for allowing external parties to use Control Panel's APIs
- SessionAuthentication
- JWTAuthentication(Oauth2 flow): mainly for Machine to Machine API call
  we use Auth0 as the oauth server to produce the access token. 
  The process for granting the access to Control panel's API
  - Register a machine-to-machine auth0 client for this external party
  - Grant the access to Control panel APIs from auth0:
    Applications>APIs>`Control panel APIs`>`Machine To Machine Applications`
  - Choose the suitable scopes for this third party there
  
  