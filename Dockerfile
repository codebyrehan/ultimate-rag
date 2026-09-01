FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS backend-builder
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HUB_DISABLE_TELEMETRY=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml ./
COPY backend/ultimate_rag/ ./ultimate_rag/
RUN pip install --no-cache-dir -e ".[prod]"
COPY backend/ ./
RUN python -c "import ultimate_rag"

FROM python:3.12-slim AS production
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HUB_DISABLE_TELEMETRY=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=frontend-builder /app/frontend/dist/ /app/frontend-dist/
COPY --from=backend-builder /app /app
COPY --from=backend-builder /usr/local /usr/local
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/health || exit 1
ENTRYPOINT ["/app/entrypoint.sh"]
