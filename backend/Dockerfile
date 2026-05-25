FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /workspace

# Copy workspace manifests (layer-cached)
COPY pyproject.toml uv.lock* ./
COPY backend/pyproject.toml ./backend/
COPY lsapi/pyproject.toml ./lsapi/
COPY lsapi/src/ ./lsapi/src/

# Install production deps only
RUN uv sync --frozen --no-dev

# Copy source
COPY backend/ ./backend/
COPY lsapi/ ./lsapi/

WORKDIR /workspace/backend

CMD ["uv", "run", "gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
