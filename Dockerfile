FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    COCKPIT_DATA_DIR=/data \
    TZ=Europe/Berlin

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY cockpit ./cockpit
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4)" || exit 1

# The entrypoint starts as root only to fix ownership of /data, then runs the
# app as PUID:PGID (default 1000:1000).
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# One worker with threads: the reminder scheduler must run exactly once.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", \
     "--timeout", "60", "--worker-tmp-dir", "/tmp", "--no-control-socket", \
     "cockpit:create_app()"]
