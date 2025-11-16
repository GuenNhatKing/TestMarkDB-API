#!/usr/bin/env bash
set -e

cd /app/server

if [ "$PROD" = "true" ]; then
  if [ "$RUN_APP" = "true" ]; then
    python manage.py collectstatic --noinput
    python manage.py makemigrations app --noinput || true
    python manage.py makemigrations --noinput || true
    python manage.py migrate --noinput
    exec uwsgi --ini ./uwsgi.ini
  elif [ "$RUN_CELERY" = "true" ]; then
    python -m http.server 8080 &
    exec celery -A root worker --loglevel=INFO --pool=threads
  else
    exit 1
  fi
else
  python manage.py collectstatic --noinput
  python manage.py makemigrations app --noinput || true
  python manage.py makemigrations --noinput || true
  python manage.py migrate --noinput
  exec "$@"
fi
