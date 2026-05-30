# BicQuant

## Development Setup

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- [Node.js](https://nodejs.org/) v20+

### 1. Clone the repository

```bash
git clone git@github.com:<github-username>/bicquant.git
cd bicquant
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the required values. For local development, set `DATABASE_URL` as follows:

```env
POSTGRES_DB=bicquant
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bicquant
```

### 3. Install Python dependencies

```bash
uv sync --all-packages
```

This installs all workspace packages (`backend`, `lsapi`) and their dependencies into `.venv`.

### 4. Run services

**Terminal 1 — PostgreSQL**

```bash
docker compose -f docker-compose.dev.yml up
```

**Terminal 2 — Backend**

```bash
uv run uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000
```

**Terminal 3 — Frontend**

```bash
cd frontend
npm install
npm run dev
```

### URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
