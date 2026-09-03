# PR-Warden server image (PR-Agent github_app + Ollama-friendly).
# Build once, run forever. Model runs via OLLAMA_API_BASE (host or container).

FROM python:3.12-slim

WORKDIR /app

# Runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install PR-Agent engine (upstream MIT)
RUN pip install --no-cache-dir "pr-agent"

# Warden launcher + config
COPY src/run_server.py /app/run_server.py
COPY config/warden.toml.example /app/config/warden.toml.example
COPY .env.example /app/.env.example

ENV PORT=3000
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUTF8=1
ENV CONFIG__FALLBACK_MODELS=""
ENV CONFIG__CUSTOM_MODEL_MAX_TOKENS=32000

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:3000/ || exit 1

CMD ["python", "run_server.py"]
