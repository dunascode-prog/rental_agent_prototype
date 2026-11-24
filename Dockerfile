# Container image for the Option B demo (ECS Fargate + EFS, docs/DEPLOYMENT.md).
# Runs as a non-root user (uid 1000). The SQLite file lives on the /data volume.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/app.db

WORKDIR /srv/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY projects ./projects

RUN useradd --uid 1000 --create-home appuser \
    && mkdir -p /data \
    && chown appuser /data
USER 1000

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
