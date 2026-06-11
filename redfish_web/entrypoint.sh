#!/bin/sh
set -e

echo "[web] Running migrations..."
python manage.py migrate --no-input

echo "[web] Initialising emulator hosts..."
python manage.py init_emulator_hosts || echo "[web] init_emulator_hosts skipped (no EMULATOR_URL set)"

echo "[web] Starting Django..."
exec python manage.py runserver 0.0.0.0:8000
