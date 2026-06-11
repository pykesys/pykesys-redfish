#!/usr/bin/env bash
#
# Production startup — Django web app via gunicorn
#
# Usage:
#   ./run.sh
#
# Environment:
#   DJANGO_SECRET_KEY   Required in production
#   DEBUG               Set to "false" in production
#   PORT                Bind port (default: 8000)
#   WORKERS             Gunicorn worker count (default: 4)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="${SCRIPT_DIR}/redfish_web"

PORT="${PORT:-8000}"
WORKERS="${WORKERS:-4}"

cd "${WEB_DIR}"

echo "[run.sh] Running migrations..."
python manage.py migrate --no-input

echo "[run.sh] Collecting static files..."
python manage.py collectstatic --no-input --clear 2>/dev/null || true

echo "[run.sh] Starting gunicorn on 0.0.0.0:${PORT} (workers: ${WORKERS})..."
exec gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WORKERS}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    redfish_web.wsgi
