HOST=0.0.0.0
PORT=8000
PROJECT=control-panel
MODULE=control_panel_api
VENV=venv
ifneq (${USE_VENV}, false)
	BIN=${VENV}/bin
	USE_VENV=true
else
	BIN=/usr/bin
endif

-include .env
export

.PHONY: collectstatic createdb createuser dependencies help migrations nocreatedb nocreateuser run test wait_for_db

venv/bin:
	@if ${USE_VENV} && [ ! -d "${VENV}" ] ; then python3 -m venv venv ; fi

usr/bin:

## dependencies: Install dependencies
dependencies: ${BIN} requirements.txt
	@echo
	@echo "> Fetching dependencies..."
	@${BIN}/pip3 install -r requirements.txt

## collectstatic: Collect assets into static folder
collectstatic:
	@echo
	@echo "> Collecting static assets..."
	@${BIN}/python3 manage.py collectstatic

## run: Run webapp
run:
	@echo
	@echo "> Running webapp..."
	@${BIN}/gunicorn -b ${HOST}:${PORT} ${MODULE}.wsgi:application

wait_for_db:
	@echo
	@echo "> Waiting for database..."
	@${BIN}/python3 wait_for_db

## shell: Run Django shell
shell:
	@echo
	@echo "> Running shell..."
	@${BIN}/python3 manage.py shell_plus

## test: Run tests
test: export DJANGO_SETTINGS_MODULE=${MODULE}.settings.test
test: wait_for_db
	@echo
	@echo "> Running tests..."
	@NAMED_TESTS="$(shell if [ -n "${TEST_NAME}" ]; then echo "-k ${TEST_NAME}" ; fi)" && \
	${BIN}/pytest --color=yes ${MODULE} $$NAMED_TESTS

## migrations: Apply database migrations
migrations: wait_for_db
	@echo
	@echo "> Running database migrations..."
	@${BIN}/python3 manage.py migrate

createuser:
	@echo "Creating user ${DB_USER}"
	@createuser -d ${DB_USER}

nocreateuser:
	@echo User ${DB_USER} already exists

createdb:
	@echo "Creating database ${DB_NAME}"
	@createdb -U ${DB_USER} ${DB_NAME}

nocreatedb:
	@echo Database ${DB_NAME} already exists

## init-database: Setup database and user
init-database:
	@echo
	@echo "> Initializing database..."
	@make $(shell psql postgres -tAc "SELECT 'no' FROM pg_roles WHERE rolname='${DB_USER}'")createuser
	@make $(shell psql postgres -tAc "SELECT 'no' FROM pg_database WHERE datname='${DB_NAME}'")createdb

## docker-image: Build docker image
docker-image:
	@echo
	@echo "> Building docker image..."
	@docker build -t ${PROJECT} .

install-helm:
	@wget https://storage.googleapis.com/kubernetes-helm/helm-v${HELM_VERSION}-linux-amd64.tar.gz -O helm.tgz && \
		tar fxz helm.tgz && \
		mv linux-amd64/helm /usr/local/bin && \
		rm -rf helm.tgz linux-amd64

## superuser: Create a superuser
superuser:
	@echo
	@echo "> Creating superuser..."
	@read -p "Username: " username; \
	read -s -p "Password: " password; \
	${BIN}/python3 manage.py shell -c "from control_panel_api.models import User; u = User(); u.username='$$username'; u.set_password('$$password'); u.is_superuser=True; u.save()"

## docker-test: Run tests in Docker container
docker-test:
	@echo
	@echo "> Running tests in Docker..."
	@docker-compose -f docker-compose.test.yml run app make test TEST_NAME=$$TEST_NAME

help: Makefile
	@echo
	@echo " Commands in "$(PROJECT)":"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' | sed -e 's/^/ /'
	@echo
