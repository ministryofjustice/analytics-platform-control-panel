#!/usr/bin/env bash

# Upgrade NPM
npm install --global npm@latest

# Start Postgres
docker compose --file contrib/docker-compose-postgres.yml up --detach

# Start Redis
docker compose --file contrib/docker-compose-redis.yml up --detach

# Add helm repo
helm repo add mojanalytics http://moj-analytics-helm-repo.s3-website-eu-west-1.amazonaws.com
helm repo update

# Upgrade Pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
pip install -r requirements.dev.txt

# install npm dependencies and static assets
npm install
make build-static

# Run migrations
python manage.py migrate
