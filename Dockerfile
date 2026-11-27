FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DOKUMENTE_ROOT=/data/dokumente

WORKDIR /app

# Systemabhängigkeiten für Healthcheck, gosu (Privilege Drop) und sauberen Build
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gosu \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten zuerst installieren (Docker Layer Caching)
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Anwendungscode und Alembic-Konfiguration kopieren
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app/ ./app/
COPY entrypoint.sh .

RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /data/dokumente

# Nicht-Root-Benutzer für sicheren NAS-Betrieb (entrypoint.sh wechselt nach chown auf appuser)
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser \
    && chown -R appuser:appgroup /app /data/dokumente

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
