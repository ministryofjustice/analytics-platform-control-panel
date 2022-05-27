REPOSITORY?=controlpanel
VIRTUAL_ENV ?= venv
BIN=${VIRTUAL_ENV}/bin
IMAGE_TAG ?= local
DOCKER_BUILDKIT?=1
REGISTRY?=593291632749.dkr.ecr.eu-west-1.amazonaws.com
MAKEFLAGS += -j2
REGION?=eu-west-1
AWS_PROFILE?=admin-dev

include Makefile.local.mk
export

.PHONY: clean build help test test-python dev-up

clean:
	docker-compose down --volumes --remove-orphans

build:
	@docker-compose build frontend_eks

eks:
	@docker-compose build frontend_eks

test-python: DJANGO_SETTINGS_MODULE=controlpanel.settings.test
test-python:
	@echo
	@echo "> Running Python Tests (In Docker)..."
	@docker-compose run --rm -e KUBECONFIG=tests/kubeconfig \
		frontend sh -c "pytest tests --color=yes"

## test: Run tests in Docker container
test: test-python

prepare-up:
	@docker-compose up -d db
	@docker-compose run --rm --no-deps frontend sh -c "do sleep 2;done"
	@docker-compose up migration
	@docker-compose run --rm --no-deps frontend sh -c "do sleep 2;done"

up: prepare-up
	@docker-compose up -d frontend
	@docker-compose logs -f

enter:
	docker-compose run --rm --no-deps --entrypoint sh worker
logs:
	@docker-compose logs -f
push:
	docker-compose push frontend
push_eks:
	docker-compose push frontend_eks

help: Makefile
	@echo
	@echo " Commands in "$(REPOSITORY)":"
	@echo
	@sed -n 's/^##//p' $< Makefile.local.mk | column -t -s ':' | sed -e 's/^/ /'
	@echo
