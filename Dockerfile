# =============================================================================
# Biomedical Equipment Troubleshooter — Production image
# Target: Google Cloud Run (stateless HTTP, PORT injected by platform)
# =============================================================================

FROM python:3.12-slim AS base

# ----- Runtime environment -----------------------------------------------------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    PORT=8080

# ----- System packages --------------------------------------------------------
# build-essential only present in the build stage; final image stays slim.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ----- App user (non-root) ----------------------------------------------------
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

# ----- Python deps ------------------------------------------------------------
# Copy requirements first so layer caching survives code-only edits.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ----- Application code -------------------------------------------------------
COPY src/         ./src/
COPY data/        ./data/
COPY langgraph.json ./langgraph.json
COPY pyproject.toml ./pyproject.toml
COPY README.md    ./README.md

RUN chown -R app:app /app
USER app

# ----- Healthcheck ------------------------------------------------------------
# Cloud Run itself probes the port; this HEALTHCHECK helps when running in
# plain Docker / Compose. Adjust PORT below if you override at build time.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/healthz" || exit 1

# ----- Entry point ------------------------------------------------------------
# Cloud Run sets PORT at runtime. `sh -c` so ${PORT} expands inside the
# container. --workers is intentionally 1: the graph compiles once per worker
# and Cloud Run already scales horizontally via replicas.
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 75"]
