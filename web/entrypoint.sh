#!/bin/sh
set -e
# Sin .env: genera una clave propia y la conserva en el volumen para no cerrar sesiones al reiniciar.
if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  key_file=/data/.django_secret_key
  if [ ! -s "$key_file" ]; then
    (umask 077 && python -c "import secrets; print(secrets.token_urlsafe(64))" > "$key_file")
  fi
  DJANGO_SECRET_KEY="$(cat "$key_file")"
  export DJANGO_SECRET_KEY
fi
python manage.py migrate --noinput
python manage.py seed_demo
exec gunicorn optiflow.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 45 --access-logfile -
