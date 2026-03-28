FROM python:3.12-slim

WORKDIR /app

# Install Node.js for frontend build
RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build frontend
COPY ui/package*.json ui/
RUN cd ui && npm install
COPY ui/ ui/
RUN cd ui && npm run build

# Copy backend + config + templates
COPY src/ src/
COPY config/ config/
COPY templates/ templates/
COPY examples/ examples/

# Persistent volume mount point (Railway mounts here)
RUN mkdir -p /data/db

# Railway sets PORT env var
ENV PORT=8000
ENV CLOUD_MODE=1
ENV DB_PATH=/data/db/pipeline.db
ENV DATA_DIR=/data

EXPOSE 8000

CMD python -m uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}
