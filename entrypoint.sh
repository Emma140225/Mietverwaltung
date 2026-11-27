#!/usr/bin/env bash
set -euo pipefail

DOK_DIR="${DOKUMENTE_ROOT:-/data/dokumente}"

# Stellt sicher, dass der über die NAS-UI erstellte Ordner für appuser beschreibbar ist
mkdir -p "${DOK_DIR}"
chown -R appuser:appgroup "${DOK_DIR}"

echo "[entrypoint] Führe Datenbank-Migrationen aus (alembic upgrade head)..."
gosu appuser alembic upgrade head

echo "[entrypoint] Starte Uvicorn ASGI-Server..."
exec gosu appuser uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level "${LOG_LEVEL:-info}"
