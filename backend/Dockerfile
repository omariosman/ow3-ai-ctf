# Build context is the repository root (see docker-compose.yml) so the image can
# include both the backend package and the shared challenges/ metadata.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY challenges /challenges

# Persisted data (SQLite db + server-side flag store) live under /data.
ENV CTF_DATABASE_URL=sqlite:////data/ctf.db \
    CTF_SECRETS_DIR=/data/.secrets
VOLUME ["/data"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
