REPOSITORY?=controlpanel
VIRTUAL_ENV ?= venv
BIN=${VIRTUAL_ENV}/bin
IMAGE_TAG ?= local
DOCKER_BUILDKIT?=1
REGISTRY?=593291632749.dkr.ecr.eu-west-1.amazonaws.com
MAKEFLAGS += -j2

include Makefile.local.mk
export

.PHONY: clean build help test test-python dev-up

clean:
	docker-compose down --volumes --remove-orphans

build:
	@docker-compose build frontend

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

help: Makefile
	@echo
	@echo " Commands in "$(REPOSITORY)":"
	@echo
	@sed -n 's/^##//p' $< Makefile.local.mk | column -t -s ':' | sed -e 's/^/ /'
	@echo

build-static:
	make build-css
	make build-js
	python3 manage.py collectstatic

build-css:
	mkdir static
	mkdir -p static/assets/fonts
	mkdir -p static/assets/images
	cp -R node_modules/govuk-frontend/dist/govuk/assets/fonts/. static/assets/fonts
	cp -R node_modules/govuk-frontend/dist/govuk/assets/images/. static/assets/images
	cp -R node_modules/accessible-autocomplete/dist/ static/accessible-autocomplete
	cp -R node_modules/govuk-frontend/ static/govuk-frontend
	cp -R node_modules/@ministryofjustice/frontend/ static/ministryofjustice-frontend
	cp -R node_modules/html5shiv/dist/ static/html5-shiv
	npm run css --load

build-js:
	mkdir -p static/assets/js
	cp node_modules/govuk-frontend/dist/govuk/govuk-frontend.min.js static/assets/js/govuk-frontend.min.js
	cp node_modules/govuk-frontend/dist/govuk/govuk-frontend.min.js.map static/assets/js/govuk-frontend.min.js.map

	cp -R node_modules/jquery/dist/ static/jquery
	cp -R node_modules/jquery-ui/dist/ static/jquery-ui
	./node_modules/.bin/babel \
  controlpanel/frontend/static/module-loader.js \
  controlpanel/frontend/static/components \
  controlpanel/frontend/static/javascripts \
  -o static/app.js -s

serve-sso:
	aws-sso exec --profile analytical-platform-development:AdministratorAccess --no-region -- python manage.py runserver

celery-sso:
	aws-sso exec --profile analytical-platform-development:AdministratorAccess --no-region -- celery -A controlpanel worker --loglevel=info

db-migrate:
	python manage.py migrate

db-drop:
	python manage.py reset_db
