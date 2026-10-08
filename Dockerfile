FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REGEN_DATABASE_PATH=/data/regen.sqlite3

WORKDIR /app

COPY requirements-api.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt \
    && mkdir -p /data \
    && chown 10001:10001 /data

COPY regen_api ./regen_api

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "regen_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
