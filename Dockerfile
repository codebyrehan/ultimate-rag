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
        nginx \
        curl \
        gettext \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default
COPY frontend/nginx.conf.template /etc/nginx/conf.d/default.conf.template
COPY --from=frontend-builder /app/frontend/dist/ /var/www/html/
COPY --from=backend-builder /app /app
COPY --from=backend-builder /usr/local /usr/local
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app /var/www/html /var/log/nginx /var/lib/nginx \
    && chmod +x /app/entrypoint.sh
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
ENTRYPOINT ["/app/entrypoint.sh"]
