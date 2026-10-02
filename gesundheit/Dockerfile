# Gesundheits-Cockpit. Build from the repository root, because the design is shared with the
# Projekt-Cockpit:   docker compose up -d --build   (in this folder; see docker-compose.yml)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GESUNDHEIT_DATA_DIR=/data \
    GESUNDHEIT_SHARED_DIR=/app/shared \
    TZ=Europe/Berlin

WORKDIR /app

COPY gesundheit/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gesundheit/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# Shared design: stylesheet, scripts, fonts and the error page graphics of the cockpit.
COPY cockpit/static ./shared/static
COPY cockpit/templates/_grafiken.html ./shared/templates/_grafiken.html
COPY gesundheit/gesundheit ./gesundheit
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh

VOLUME ["/data"]
EXPOSE 6767

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6767/health', timeout=4)" || exit 1

# The entrypoint starts as root only to fix ownership of /data, then runs the
# app as PUID:PGID (default 1000:1000).
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# One worker with threads: the hourly sync and the imports must run exactly once.
CMD ["gunicorn", "--bind", "0.0.0.0:6767", "--workers", "1", "--threads", "8", \
     "--timeout", "120", "--worker-tmp-dir", "/tmp", "--no-control-socket", \
     "gesundheit:create_app()"]
