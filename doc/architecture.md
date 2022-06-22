# Architecture

This document is to show the key design and implementation of this application, but it won't go down in very defail
level. The best way to know very detail code leve is to read the codes

## System overview
![System Overview](./images/system_overview.png "The system overview of the app")

The system diagram above shows how many external tools/services/platform the control panel interacts with, which partially
explain the complicated part in this app is not the users' requirement, but the integration with
different external systems. A few extra points
- User authenticating to the control panel via github through Auth0.
- The main infrastructure the app communicates is AWS platform including IAM, SSM, SecretManager, EKS clusters.
- Each interaction with external system requires authentication + authorisation process, especially for AWS platform. 
  Due to the reason of trying to manage different resources and clusters easier and secure, control panel needs to 
  access different AWS accounts.

## Authentication

Every external system/service the control panel app interacts with needs an authentication process, majority of them 
is to have credentials (e.g., client_id and client_secret) benign provided as kubernetes secret,  control panel will 
request a new token per request to external system/service.  

![Authentication Overview](./images/authentication.png "The authentications of the app")

### User login to control panel flow

we

### User login to tooling flow through control panel


### User login to AWS console flow through control panel


## code structure overview

The slightly complicated part is the interactions to AWS 
services and cluster, which is shown in the following diagram. 

![Code structure](./images/code_structure.png "The code structure of the app")



