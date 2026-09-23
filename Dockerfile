FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    CISIA_LLM=0 \
    CISIA_AUTH=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker/entrypoint-web.sh docker/entrypoint-retrain.sh

RUN mkdir -p data/curated data/raw models/registry models/benchmark models/gguf

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
  CMD wget -q -O- http://127.0.0.1:8000/api/health || exit 1

ENTRYPOINT ["/app/docker/entrypoint-web.sh"]
