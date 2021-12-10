
# Changelog

## v0.29.0 (10-12-2021)

### New Features
* First Phase of Prometheus Metrics
* Reset Home for EKS
* On user list show migration to EKS state
* StructLog (json based logging)

### Changes
* Switch to Python 3.9 base image
* Stop pushing built image to Quay in Github Actions.
* Using latest version of sentry client.
* Tracking Trace ID via signals
* Users created now get managed airflow user roles

### Fixes
* Fix the docker-compose link configuration

### Documentation
* Adding in the data structure visualisation
* Direct linking to the relevant docs
* Update the deployment documentation to reference EKS and NotKS differences, as well as more detail.

### Dependancy Updates
* pylint-django from 2.0.15 to 2.4.4
* channels-redis from 3.0.1 to 3.3.1
* django-extensions from 3.0.8 to 3.1.5
* mozilla-django-oidc from 1.2.4 to 2.0.0
* urllib3 from 1.25.10 to 1.26.7
* psycopg2-binary from 2.8.5 to 2.9.2
* django-structlog from 2.1.3 to 2.2.0
* tmpl from 1.0.4 to 1.0.5
* boto3 from 1.14.55 to 1.20.13 
* djangorestframework from 3.11.1 to 3.12.4
* rules from 2.2 to 3.0

### Cleanup
* Remove the following requirements
  * Twisted
  * service-identity
  * Botocore (its an existing subdependency)
