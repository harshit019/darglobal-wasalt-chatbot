# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=7860

# Install curl for container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000 is recommended by Hugging Face Spaces)
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# Install Python runtime dependencies first for Docker layer caching
COPY --chown=user:user requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code, frontend assets, and scraped knowledge base
COPY --chown=user:user app/ ./app/
COPY --chown=user:user static/ ./static/
COPY --chown=user:user data/ ./data/

USER user

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD sh -c 'curl -fsS "http://localhost:${PORT:-7860}/api/health" || exit 1'

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
