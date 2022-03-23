all: help

## docker-login: Authenticate docker with ECR
docker-login:
	aws-vault exec admin-data -- aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin $(REGISTRY)

## dev-prepare-up: Run migration before doing up
dev-prepare-up:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml run migration

## dev-daemon: Startup with docker process in background (to stop afterwards use make clean)
dev-daemon: dev-prepare-up
	docker-compose -f docker-compose.yaml -f  docker-compose.dev.yaml up -d frontend

## dev-fg: Startup with docker process in foreground
dev-fg: dev-prepare-up
	docker-compose -f docker-compose.yaml -f  docker-compose.dev.yaml up frontend

## dev-debug: Startup clean docker process in background, and docker attach to foreground for debugging
dev-debug: clean dev-daemon
	docker attach $(shell sh -c "docker-compose ps -q frontend")

## dev-attach: Attach to existing running background docker process for purposes of debugging
dev-attach:
	docker attach $(shell sh -c "docker-compose ps -q frontend")

## dev-py: Start django shell (in the dev-packages context) in new container
dev-py:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml run frontend sh -c "dev-packages/bin/python manage.py shell"

## dev-run: Start shell in new copy of container
dev-run:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml run --rm frontend bash

## dev-exec: Exec into shell of existing container
dev-exec:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml exec frontend bash

test-wip: DJANGO_SETTINGS_MODULE=controlpanel.settings.test
test-wip:
	@echo
	@echo "> Running Python Tests (In Docker)..."
	@docker-compose -f docker-compose.yaml -f  docker-compose.dev.yaml run --rm -e KUBECONFIG=tests/kubeconfig \
		frontend sh -c "pytest tests --color=yes -m indevelopment"
