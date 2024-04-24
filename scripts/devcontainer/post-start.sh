#!/usr/bin/env bash

# Run pre-commit
pre-commit install

aws-sso config-profiles

aws-sso exec --profile analytical-platform-development:AdministratorAccess -- aws eks --region eu-west-1 update-kubeconfig --name development-aWrhyc0m --alias dev-eks-cluster
kubectl config use-context dev-eks-cluster
