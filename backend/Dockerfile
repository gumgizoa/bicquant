FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /workspace

# Copy workspace manifests (layer-cached)
COPY pyproject.toml uv.lock* ./
COPY backend/pyproject.toml ./backend/
COPY lsapi/pyproject.toml ./lsapi/
COPY lsapi/src/ ./lsapi/src/
COPY dartapi/pyproject.toml ./dartapi/
COPY dartapi/src/ ./dartapi/src/
COPY kofiaapi/pyproject.toml ./kofiaapi/
COPY kofiaapi/src/ ./kofiaapi/src/

# Install production deps only
RUN uv sync --frozen --no-dev

# Copy source
COPY backend/ ./backend/
COPY lsapi/ ./lsapi/
COPY dartapi/ ./dartapi/
COPY kofiaapi/ ./kofiaapi/

WORKDIR /workspace/backend

CMD ["uv", "run", "gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
