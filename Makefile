REPOSITORY?=controlpanel_eks
VIRTUAL_ENV ?= venv
BIN=${VIRTUAL_ENV}/bin
IMAGE_TAG ?= local
DOCKER_BUILDKIT?=1
REGISTRY?=593291632749.dkr.ecr.eu-west-1.amazonaws.com
MAKEFLAGS += -j2
REGION?=eu-west-1

include Makefile.local.mk
export

.PHONY: clean build help test test-python dev-up

## clean: Bring all containers down and remove orphan volumes.
clean:
	docker-compose down --volumes --remove-orphans

build:
	@docker-compose build frontend

test-python: DJANGO_SETTINGS_MODULE=controlpanel.settings.test
test-python:
	@echo
	@echo "> Running Python Tests (In Docker)..."
	@docker-compose run --rm \
		frontend sh -c "./run_tests.sh"

## test: Run tests in Docker container
test: test-python

## test-local: Build and run tests
test-local: build test

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

push_eks:
	docker-compose push frontend

help: Makefile
	@echo
	@echo " Commands in "$(REPOSITORY)":"
	@echo
	@sed -n 's/^##//p' $< Makefile.local.mk | column -t -s ':' | sed -e 's/^/ /'
	@echo
