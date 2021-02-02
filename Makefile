REPOSITORY?=controlpanel
VIRTUAL_ENV ?= venv
BIN=${VIRTUAL_ENV}/bin
IMAGE_TAG ?= local
DOCKER_BUILDKIT?=1
REGISTRY?=593291632749.dkr.ecr.eu-west-1.amazonaws.com
NETWORK?=default
MAKEFLAGS += -j2

include Makefile.local.mk
export

.PHONY: clean build help test test-python dependencies collectstatic node_modules compilescss transpile clean-bytecode dev-up

clean:
	docker-compose down --volumes --remove-orphans

build:
	@docker-compose build frontend

## docker-test: Run tests in Docker container
test-python: DJANGO_SETTINGS_MODULE=controlpanel.settings.test
test-python:
	@echo
	@echo "> Running Python Tests (In Docker)..."
	@docker-compose run --rm -e KUBECONFIG=tests/kubeconfig \
		frontend sh -c "until pg_isready -h db; do sleep 2; done; pytest tests --color=yes"

test: test-python

up:
	@docker-compose up -d db
	@docker-compose run --rm --no-deps frontend sh -c "until pg_isready -h db; do sleep 2;done"
	@docker-compose up migration
	@docker-compose run --rm --no-deps frontend sh -c "until pg_isready -h db; do sleep 2;done"
	@docker-compose up -d frontend
	@docker-compose logs -f

logs:
	@docker-compose logs -f
push:
	docker-compose push frontend

help: Makefile
	@echo
	@echo " Commands in "$(REPOSITORY)":"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' | sed -e 's/^/ /'
	@echo
