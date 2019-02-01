HOST=0.0.0.0
PORT=8000
PROJECT=control-panel
MODULE=control_panel_api
VENV=venv
BIN=${VENV}/bin

-include .env
export

.PHONY: collectstatic dependencies help run test wait_for_db

venv/bin:
	@if ${USE_VENV} && [ ! -d "${VENV}" ] ; then python3 -m venv ${VENV} ; fi

## dependencies: Install dependencies
dependencies: ${BIN} requirements.txt
	@echo
	@echo "> Fetching dependencies..."
	@${BIN}/pip3 install -r requirements.txt

## collectstatic: Collect assets into static folder
collectstatic: dependencies
	@echo
	@echo "> Collecting static assets..."
	@${BIN}/python3 manage.py collectstatic --noinput

## run: Run webapp
run: collectstatic
	@echo
	@echo "> Running webapp..."
	@${BIN}/gunicorn -b ${HOST}:${PORT} ${MODULE}.wsgi:application

wait_for_db:
	@echo
	@echo "> Waiting for database..."
	@${BIN}/python3 wait_for_db

## test: Run tests
test: export DJANGO_SETTINGS_MODULE=${MODULE}.settings.test
test: wait_for_db
	@echo
	@echo "> Running tests..."
	@NAMED_TESTS="$(shell if [ -n "${TEST_NAME}" ]; then echo "-k ${TEST_NAME}" ; fi)" && \
	${BIN}/pytest --color=yes ${MODULE} $$NAMED_TESTS

## docker-image: Build docker image
docker-image:
	@echo
	@echo "> Building docker image..."
	@docker build -t ${PROJECT} .

## docker-test: Run tests in Docker container
docker-test:
	@echo
	@echo "> Running tests in Docker..."
	@docker-compose -f docker-compose.test.yml up --abort-on-container-exit

help: Makefile
	@echo
	@echo " Commands in "$(PROJECT)":"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' | sed -e 's/^/ /'
	@echo
