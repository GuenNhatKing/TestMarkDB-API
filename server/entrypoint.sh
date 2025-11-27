#!/usr/bin/env bash
set -e

cd /app/server
python manage.py collectstatic --noinput

if [ "$PROD" = "true" ]; then
  echo "Running in production mode"
  if [ "$RUN_APP" = "true" ]; then
    echo "Starting uWSGI application server"
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
  exec "$@"
fi
