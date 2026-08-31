FROM python:3.12-slim

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

# Add non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY backend/pyproject.toml backend/ultimate_rag/ ./

RUN pip install --no-cache-dir -e ".[prod]"

COPY backend/ ./

RUN python -c "import ultimate_rag"

# Create data dir for appuser
RUN mkdir -p /app/data && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "ultimate_rag.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
