HOST=0.0.0.0
PORT=8000
PROJECT=controlpanel
MODULE=controlpanel
VIRTUAL_ENV ?= venv
BIN=${VIRTUAL_ENV}/bin
DEV=true

-include .env
export

.PHONY: clean clean-bytecode clean-static collectstatic compilescss dependencies docker-image docker-test help node_modules run test transpile


clean-static:
	@echo
	@echo "> Removing collected static files..."
	@rm -rf run/static static/*

clean-bytecode:
	@echo
	@echo "> Removing compiled bytecode..."
	@find controlpanel -name '__pycache__' -d -prune -exec rm -r {} +

clean: clean-bytecode clean-static

${BIN}:
	@if [ -z "$$NO_VIRTUAL_ENV" -a ! -d "${VIRTUAL_ENV}" ]; then echo "\n> Initializing virtualenv..."; python3 -m venv ${VIRTUAL_ENV}; fi

## dependencies: Install dependencies
dependencies: ${BIN} requirements.txt
	@echo
	@echo "> Fetching dependencies..."
	@${BIN}/pip3 install -r requirements.txt
	@${BIN}/pip3 freeze > requirements.lock
	@if [ ! "${DEV}" = "false" ]; then ${BIN}/pip3 install -r requirements.dev.txt; fi

## collectstatic: Collect assets into static folder
collectstatic: dependencies node_modules compilescss transpile
	@echo
	@echo "> Collecting static assets..."
	@${BIN}/python3 manage.py collectstatic --noinput

node_modules:
	@echo
	@echo "> Installing Javascript dependencies..."
	@npm install
	@cp -R node_modules/accessible-autocomplete/dist/ static/accessible-autocomplete
	@cp -R node_modules/govuk-frontend/ static/govuk-frontend
	@cp -R node_modules/@hmcts/frontend/ static/hmcts-frontend
	@cp -R node_modules/html5shiv/dist/ static/html5-shiv
	@cp -R node_modules/jquery/dist/ static/jquery

compilescss:
	@echo
	@echo "> Compiling SCSS..."
	@npm run css

transpile:
	@echo
	@echo "> Transpiling ES6..."
	@npm run babel

redis:
	@echo
	@echo "> Running Redis server..."
	@if [ -z "$$REDIS_PASSWORD" ]; then REQUIREPASS="--requirepass=$$REDIS_PASSWORD"; fi
	@redis-server $$REQUIREPASS &>/tmp/redis.log &

## run: Run webapp
run: export DJANGO_SETTINGS_MODULE=${MODULE}.settings.development
run: collectstatic redis
	@echo
	@echo "> Running webapp..."
	@${BIN}/python3 manage.py runserver

run-worker: export DJANGO_SETTINGS_MODULE=${MODULE}.settings.development
run-worker: redis
	@echo
	@echo "> Running background task worker..."
	@${BIN}/python3 manage.py runworker background_tasks

## test: Run tests
test: export DJANGO_SETTINGS_MODULE=${MODULE}.settings.test
test:
	@echo
	@echo "> Running tests..."
	${BIN}/pytest --color=yes && npm run test -- --coverage

## docker-image: Build docker image
docker-image:
	@echo
	@echo "> Building docker image..."
	@docker build -t ${PROJECT} .

## docker-run: Run app in a Docker container
docker-run: redis
	@echo
	@echo "> Run docker container..."
	@docker run \
		-v ${HOME}/.kube/config:/home/${PROJECT}/.kube/config \
		-p ${PORT}:${PORT} \
		--env-file=.env \
		-e ALLOWED_HOSTS="*" \
		-e DB_HOST=host.docker.internal \
		-e DB_NAME=${PROJECT} \
		-e DB_USER=${PROJECT} \
		-e DEBUG=True \
		-e REDIS_HOST=host.docker.internal \
		${PROJECT}

## docker-test: Run tests in Docker container
docker-test:
	@echo
	@echo "> Running tests in Docker..."
	@docker-compose run \
		-e DJANGO_SETTINGS_MODULE=${MODULE}.settings.test \
		-e KUBECONFIG=tests/kubeconfig \
		cpanel sh -c "until pg_isready -h db; do sleep 2; done; pytest tests --color=yes && npm run test -- --coverage"

help: Makefile
	@echo
	@echo " Commands in "$(PROJECT)":"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' | sed -e 's/^/ /'
	@echo
