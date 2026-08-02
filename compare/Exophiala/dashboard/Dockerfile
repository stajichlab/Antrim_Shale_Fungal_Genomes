# ---------------------------------------------------------------------------
# BFD chat server — FastAPI + DuckDB NL→SQL chatbot
# ---------------------------------------------------------------------------
# Build:
#   docker build -t bfd-chat:latest -f compare/Exophiala/dashboard/Dockerfile compare/Exophiala/
#
# Run locally:
#   docker run --rm -p 8811:8000 \
#     -v $(pwd)/compare/Exophiala/db/BFD.duckdb:/data/BFD.duckdb:ro \
#     -e BFD_DUCKDB_PATH=/data/BFD.duckdb \
#     -e ANTHROPIC_API_KEY \
#     bfd-chat:latest
#
#   # or with NRP.ai custom LLM:
#   docker run --rm -p 8811:8000 \
#     -v $(pwd)/compare/Exophiala/db/BFD.duckdb:/data/BFD.duckdb:ro \
#     -e BFD_DUCKDB_PATH=/data/BFD.duckdb \
#     -e CUSTOM_LLM_BASE_URL="https://ellm.nrp-nautilus.io/v1" \
#     -e CUSTOM_LLM_MODEL="qwen3" \
#     -e OPENAI_API_KEY \
#     bfd-chat:latest
#
# Open: http://localhost:8811/
# ---------------------------------------------------------------------------

FROM python:3.11-slim

LABEL maintainer="James Stajich Lab"
LABEL description="BFD comparative-genomics natural-language DuckDB explorer"

WORKDIR /app

# Install runtime dependencies in one layer.
# fastapi + uvicorn[standard] pulls in starlette, pydantic, httpx, websockets.
# duckdb's native extension (.so) ships via pip; libgomp1 is a runtime dependency.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
        "fastapi>=0.115" \
        "uvicorn[standard]>=0.32" \
        httpx \
        "duckdb>=1.1" \
        numpy \
        pandas \
        scipy

# Copy only the runtime parts (lib/ and chat/; no dashboard/build artifacts)
COPY dashboard/lib/  ./dashboard/lib/
COPY dashboard/chat/ ./dashboard/chat/

# Pre-compile Python for faster cold starts
RUN python3 -m compileall ./dashboard/lib ./dashboard/chat

# --- Security: run as non-root -----------------------------------------------
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Data volume: mount BFD.duckdb read-only at /data (Docker volume or K8s PVC mount)
VOLUME ["/data"]

EXPOSE 8000

# Health check for `docker run` and K8s livenessProbe
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import sys, urllib.request; r = urllib.request.urlopen('http://localhost:8000/health', timeout=5); sys.exit(0 if r.status == 200 else 1)"

# ENTRYPOINT uses CMD so the user can override the DB path at container start:
#   docker run ... bfd-chat:latest -- --db /my/custom/path.duckdb
# The BFD_DUCKDB_PATH env var sets the default DB path baked into the module-level
# `app` object (chat/server.py constructs it at import time).
ENTRYPOINT ["python3", "-m", "uvicorn"]
CMD ["dashboard.chat.server:app", "--host", "0.0.0.0", "--port", "8000"]
