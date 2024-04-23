#!/usr/bin/env sh

MODE=${MODE:-"run"}
ADDRESS=${ADDRESS:-"0.0.0.0"}
PORT=${PORT:-"8000"}
WORKERS=${WORKERS:-"4"}

case "$MODE" in
"run")
  echo "Running Django server on ${ADDRESS}:${PORT}"
  gunicorn -b "${ADDRESS}":"${PORT}" -k uvicorn.workers.UvicornWorker -w "${WORKERS}" controlpanel.asgi:application
  ;;
"migrate")
  echo "Running Django migrations"
  python manage.py migrate
  ;;
*)
  echo "Unknown mode: ${MODE}"
  exit 1
  ;;
esac
