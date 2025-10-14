#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py fetch_jobs

exec gunicorn jobpulse.wsgi:application --bind 0.0.0.0:8000
