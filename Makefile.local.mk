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
	@cp -R node_modules/@ministryofjustice/frontend/ static/ministryofjustice-frontend
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

clean-bytecode:
	@echo
	@echo "> Removing compiled bytecode..."
	@find controlpanel -name '__pycache__' -d -prune -exec rm -r {} +

dev-dependencies:
	docker-compose build dev-packages


prepare-dev-up:
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml run migration

dev-daemon: prepare-dev-up # Startup with docker process in background (to stop afterwards use make clean)
	aws-vault exec restricted-data -- docker-compose -f docker-compose.yaml -f  docker-compose.dev.yaml up -d frontend

dev-fg: prepare-dev-up # Startup with docker process in foreground
	aws-vault exec restricted-data -- docker-compose -f docker-compose.yaml -f  docker-compose.dev.yaml up frontend

dev-debug: clean dev-daemon # Startup clean docker process in background, and docker attach to foreground for debugging
	docker attach $(shell sh -c "docker-compose ps -q frontend")

dev-attach: # Attach to existing running background docker process for purposes of debugging
	docker attach $(shell sh -c "docker-compose ps -q frontend")

dev-py: # Start django shell (in the dev-packages context) in new container
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml run frontend sh -c "dev-packages/bin/python3 manage.py shell"

dev-run: # Start shell in new copy of container
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml run --rm frontend sh

dev-exec: # Exec into shell of existing container
	docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml exec frontend sh
