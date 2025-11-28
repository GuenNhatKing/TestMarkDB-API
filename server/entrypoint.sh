#!/usr/bin/env bash
set -e
cd /app/server

if [ "$PROD" = "true" ]; then
  if [ "$RUN_APP" = "true" ]; then
    echo "Starting uWSGI application server"
    python manage.py collectstatic --noinput
    exec uwsgi --ini ./uwsgi.ini
  elif [ "$RUN_CELERY" = "true" ]; then
    echo "Starting Celery worker"
    exec celery -A root worker --loglevel=INFO --pool=threads
  else
    echo "No valid RUN_APP or RUN_CELERY flag set. Exiting."
    exit 1
  fi
else
  echo "Running in development mode"
  if [ "$@" = "RUN_APP" ]; then
    echo "Starting uWSGI application server"
    python manage.py collectstatic --noinput
    exec uwsgi --ini ./uwsgi.ini
  elif [ "$@" = "RUN_CELERY" ]; then
    echo "Starting Celery worker"
    exec celery -A root worker --loglevel=INFO --pool=threads
  else
    echo "No valid RUN_APP or RUN_CELERY flag set. Exiting."
    exit 1
  fi
fi
