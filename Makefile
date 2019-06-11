HOST=0.0.0.0
PORT=8000
PROJECT=controlpanel
MODULE=controlpanel
VIRTUAL_ENV ?= venv
BIN=${VIRTUAL_ENV}/bin

-include .env
export

.PHONY: clean clean-bytecode clean-static collectstatic dependencies docker-image docker-test help node_modules run test


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
	@${BIN}/pip3 install -r requirements.dev.txt

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
	@./node_modules/.bin/node-sass \
		--include-path node_modules/ \
		-o static/ \
		--output-style compact \
		controlpanel/frontend/static/app.scss

transpile:
	@echo
	@echo "> Transpiling ES6..."
	@./node_modules/.bin/babel \
		controlpanel/frontend/static/module-loader.js \
		controlpanel/frontend/static/components \
		controlpanel/frontend/static/javascripts \
		-o static/app.js -s

## run: Run webapp
run: export DJANGO_SETTINGS_MODULE=${MODULE}.settings.development
run: collectstatic
	@echo
	@echo "> Running webapp..."
	@${BIN}/python3 manage.py runserver

## test: Run tests
test: export DJANGO_SETTINGS_MODULE=${MODULE}.settings.test
test:
	@echo
	@echo "> Running tests..."
	${BIN}/pytest --color=yes

## docker-image: Build docker image
docker-image:
	@echo
	@echo "> Building docker image..."
	@docker build -t ${PROJECT} .


## docker-run: Run app in a Docker container
docker-run:
	@echo
	@echo "> Run docker container..."
	@docker run \
		-v ${HOME}/.kube/config:/home/${PROJECT}/.kube/config \
		-p ${PORT}:${PORT} \
		--env-file=.env \
		-e ALLOWED_HOSTS="*" \
		-e DB_HOST=docker.for.mac.host.internal \
		-e DEBUG=True \
		${PROJECT}

## docker-test: Run tests in Docker container
docker-test:
	@echo
	@echo "> Running tests in Docker..."
	@docker-compose run \
		-e DJANGO_SETTINGS_MODULE=${MODULE}.settings.test \
		-e KUBECONFIG=tests/kubeconfig \
		app sh -c "until pg_isready -h db; do sleep 2; done; pytest tests --color=yes"

help: Makefile
	@echo
	@echo " Commands in "$(PROJECT)":"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' | sed -e 's/^/ /'
	@echo
