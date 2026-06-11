# run.sh

## Name

`run.sh` — production startup script for the pykesys-redfish Django web application

## Synopsis

```bash
./run.sh
[PORT=8000] [WORKERS=4] ./run.sh
```

## Description

`run.sh` starts the `redfish_web/` Django application via gunicorn in production mode. Before binding, it runs pending database migrations and collects static files. It is intended for production and staging deployments; for local development use `run-dashboard.sh dev` instead.

The script changes into `redfish_web/` before executing — all paths and Django settings resolve relative to that directory.

## Steps executed

1. `python manage.py migrate --no-input` — apply any pending migrations
2. `python manage.py collectstatic --no-input --clear` — collect static assets (emits a warning if SPA bundle is not built; continues)
3. `exec gunicorn ... redfish_web.wsgi` — bind and serve

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | TCP port to bind |
| `WORKERS` | `4` | Number of gunicorn sync workers |
| `DJANGO_SECRET_KEY` | *(required in production)* | Django secret key |
| `DEBUG` | `true` | Set to `false` in production |
| `EMULATOR_URL` | *(none)* | If set, `manage.py init_emulator_hosts` is called on startup |

Additional Django environment variables are documented in [README.md](../README.md#environment-variables).

## Gunicorn options

| Option | Value |
|--------|-------|
| `--bind` | `0.0.0.0:${PORT}` |
| `--workers` | `${WORKERS}` |
| `--timeout` | `120` seconds |
| `--access-logfile` | `-` (stdout) |
| `--error-logfile` | `-` (stderr) |

## Examples

```bash
# Default — bind :8000, 4 workers
./run.sh

# Override port and worker count
PORT=9000 WORKERS=8 ./run.sh

# Production with secret key
DJANGO_SECRET_KEY="$(openssl rand -hex 32)" DEBUG=false ./run.sh
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Gunicorn exited cleanly (SIGTERM received) |
| non-zero | Migration failure, port conflict, or gunicorn crash |

## Files

| Path | Description |
|------|-------------|
| `redfish_web/manage.py` | Django management script |
| `redfish_web/redfish_web/wsgi.py` | WSGI application entry point |
| `redfish_web/redfish_web/settings.py` | Django settings |

## See also

- [run-dashboard.sh](run-dashboard-sh.md) — interactive development launcher
- [README.md](../README.md) — setup and environment variable reference
- [docker-compose.yml](../docker-compose.yml) — full-stack Docker deployment
