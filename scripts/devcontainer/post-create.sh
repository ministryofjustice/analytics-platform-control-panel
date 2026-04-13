#!/usr/bin/env bash
set -e

# Start Postgres
docker compose --file contrib/docker-compose-postgres.yml up --detach

# Start Redis
docker compose --file contrib/docker-compose-redis.yml up --detach

# Add helm repo
helm repo add mojanalytics http://moj-analytics-helm-repo.s3-website-eu-west-1.amazonaws.com
helm repo update

# Install Python dependencies
rm -rf .venv
uv sync --locked
# shellcheck disable=SC1091
source .venv/bin/activate

# install npm dependencies and static assets
npm install
make build-static

# Run migrations
python manage.py migrate

# create aws and kube configs
aws-sso login
aws-sso setup profiles --force

aws-sso exec --profile analytical-platform-development:AdministratorAccess -- aws eks --region eu-west-1 update-kubeconfig --name development-aWrhyc0m --alias dev-eks-cluster
kubectl config use-context dev-eks-cluster
