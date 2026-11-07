#!/bin/sh
# Container entrypoint: the platform has no release step, so prepare the database on every boot.
# Both steps are idempotent; real reports are never wiped (the SMS replay is a staff button on /signal).
set -e

python manage.py migrate --noinput

if [ "${SEED_ON_START:-true}" = "true" ]; then
  python manage.py seed_demo --no-replay
fi

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers "${WEB_CONCURRENCY:-2}" --threads 4 --timeout 30 \
  --access-logfile -
