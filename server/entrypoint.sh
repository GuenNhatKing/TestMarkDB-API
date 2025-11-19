#!/usr/bin/env bash
set -e

cd /app/server
python manage.py collectstatic --noinput

if [ "$PROD" = "true" ]; then
  if [ "$RUN_APP" = "true" ]; then
    exec uwsgi --ini ./uwsgi.ini
  elif [ "$RUN_CELERY" = "true" ]; then
    python -m http.server 8080
    exec celery -A root worker --loglevel=INFO
  else
    exit 1
  fi
else
  exec "$@"
fi
