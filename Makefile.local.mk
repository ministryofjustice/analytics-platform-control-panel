AWS_ACCOUNT?=admin-dev
DEV_CLUSTER?=development-aWrhyc0m

all: help

## docker-login: Authenticate docker with ECR
docker-login:
	aws-vault exec $(AWS_ACCOUNT) -- aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin $(REGISTRY)

## build-local: Authenticate and build
build-local:docker-login build


## dev-prepare-up: Run migration before doing up
dev-prepare-up:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml run migration

## dev-daemon: Startup with docker process in background (to stop afterwards use make clean)
dev-daemon: dev-prepare-up
	docker-compose -f docker-compose.yaml -f  docker-compose.dev.yaml up -d frontend

## dev-worker-logs: Tail the worker container logs
dev-worker-logs: 
	aws-vault exec $(AWS_ACCOUNT) -- docker-compose -f docker-compose.yaml -f  docker-compose.dev.yaml logs -f worker

## dev-fg: Startup with docker process in foreground
dev-fg: dev-prepare-up
	aws-vault exec $(AWS_ACCOUNT) -- docker-compose -f docker-compose.yaml -f  docker-compose.dev.yaml up frontend

# dev-eks:       - exec
#       - admin-dev
#       - --
#       - aws
#       - --region
#       - eu-west-1
#       - eks
#       - get-token
#       - --cluster-name
#       - development-aWrhyc0m

## dev-debug: Startup clean docker process in background, and docker attach to foreground for debugging
dev-debug: clean dev-daemon
	docker attach $(shell sh -c "docker-compose ps -q frontend")

## dev-attach: Attach to existing running background docker process for purposes of debugging
dev-attach:
	docker attach $(shell sh -c "docker-compose ps -q frontend")

## dev-worker-attach: Attach to existing running worker docker process for purposes of debugging
dev-worker-attach:
	docker attach $(shell sh -c "docker-compose ps -q worker")

## dev-py: Start django shell (in the dev-packages context) in new container
dev-py:
	aws-vault exec $(AWS_ACCOUNT) -- docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml run frontend sh -c "dev-packages/bin/python manage.py shell"

## dev-run: Start shell in new copy of container
dev-run:
	aws-vault exec $(AWS_ACCOUNT) -- docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml run --rm frontend bash

## dev-exec: Exec into shell of existing container
dev-exec:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml exec frontend bash

test-wip: DJANGO_SETTINGS_MODULE=controlpanel.settings.test
test-wip:
	@echo
	@echo "> Running Python Tests (In Docker)..."
	@docker-compose -f docker-compose.yaml -f  docker-compose.dev.yaml run --rm -e KUBECONFIG=tests/kubeconfig \
		frontend sh -c "pytest tests --color=yes -m indevelopment"
