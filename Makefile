HOST=0.0.0.0
# PORT=8000
PROJECT=controlpanel
MODULE=controlpanel
REPOSITORY?=controlpanel
VIRTUAL_ENV ?= venv
BIN=${VIRTUAL_ENV}/bin
IMAGE_TAG ?= local
DOCKER_BUILDKIT?=1
REGISTRY?=593291632749.dkr.ecr.eu-west-1.amazonaws.com
NETWORK?=default

include Makefile.local
export

.PHONY: clean clean-bytecode clean-static collectstatic compilescss dependencies build docker-test help node_modules run test transpile

clean-bytecode:
	@echo
	@echo "> Removing compiled bytecode..."
	@find controlpanel -name '__pycache__' -d -prune -exec rm -r {} +

clean: clean-bytecode
	docker-compose down --volumes --remove-orphans

build:
	@docker-compose build frontend

js-utils:
	@echo "Building Javascript Test Container (if needed)"
	@docker build controlpanel-js-utils/ -t controlpanel-js-utils

## docker-test: Run tests in Docker container
test-python: up DJANGO_SETTINGS_MODULE=${PROJECT}.settings.test
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
	@docker-compose up worker

enter:
	docker-compose run --rm --no-deps --entrypoint sh worker
logs:
	@docker-compose logs -f
push:
	docker-compose push frontend

help: Makefile
	@echo
	@echo " Commands in "$(PROJECT)":"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' | sed -e 's/^/ /'
	@echo
