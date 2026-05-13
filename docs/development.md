# Development Guide

Local development environment setup and Git workflow for BicQuant.

---

## Table of Contents

1. [Branch Strategy](#1-branch-strategy)
2. [Local Setup](#2-local-setup)
3. [Daily Workflow](#3-daily-workflow)
4. [CI/CD Overview](#4-cicd-overview)

---

## 1. Branch Strategy

```
main          ← production (auto-deploys to EC2 on merge)
  └── develop ← integration branch
        └── feature/* ← individual feature work
```

| Branch | Purpose | Protection |
|--------|---------|-----------|
| `main` | Production-ready code | PR required, CI must pass |
| `develop` | Integration / staging | CI runs on push |
| `feature/*` | Feature development | CI runs on push |

**Rule**: Never push directly to `main`. Always go through a PR from `develop`.

---

## 2. Local Setup

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12 | `conda create -n bicquant python=3.12` |
| Node.js | ≥ 20 | via Homebrew |
| Docker Desktop | latest | https://docs.docker.com/desktop/mac/ |

### Steps

```bash
# 1. Clone
git clone git@github.com:<username>/bicquant.git
cd bicquant

# 2. Checkout develop
git checkout develop

# 3. Backend dependencies
conda activate bicquant
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt

# 4. Frontend dependencies
cd frontend && npm install && cd ..

# 5. Pre-commit hooks
pre-commit install

# 6. Environment variables
cp .env.example .env
# Fill in actual values in .env
```

### Environment Variables

See `.env.example` for all required variables. Key ones:

```env
LS_OPENAPI_APP_KEY=
LS_OPENAPI_APP_SECRET=
LS_OPENAPI_USER_ID=
TELEGRAM_BOT_TOKEN=
ANTHROPIC_API_KEY=
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<db>
FRED_API_KEY=
```

### Running Locally

```bash
# Backend (API server)
conda activate bicquant
uvicorn app.main:app --reload --app-dir backend

# Frontend (dev server with HMR)
cd frontend && npm run dev

# Full stack via Docker Compose
docker compose up --build
```

---

## 3. Daily Workflow

```bash
# 1. Start from develop (always up to date)
git checkout develop
git pull origin develop

# 2. Create a feature branch
git checkout -b feature/<name>

# 3. Work, commit
git add <files>
git commit -m "[feat] description"
# pre-commit runs ruff automatically on commit

# 4. Push → triggers CI
git push origin feature/<name>

# 5. Open PR: feature/* → develop
# 6. After CI passes, merge

# 7. When develop is ready for release → PR: develop → main
# Merging to main triggers auto-deploy to EC2
```

### Commit Message Convention

```
[feat]   new feature
[fix]    bug fix
[add]    add file / resource (non-code)
[refactor] code restructure without behavior change
[docs]   documentation only
```

---

## 4. CI/CD Overview

### Workflows

| File | Trigger | Jobs |
|------|---------|------|
| `.github/workflows/ci.yml` | push to `develop`/`feature/**`, PR to `main`/`develop` | `lint` (ruff), `test` (pytest) |
| `.github/workflows/deploy.yml` | push to `main` | Deploy to EC2 via SSH |

### CI Jobs

**lint** — Python code style check
```bash
ruff check backend/
ruff format --check backend/
```

**test** — Run test suite
```bash
pytest
```

### Local Pre-commit Hooks

The same checks run locally before every push (via `.pre-commit-config.yaml`):

- `ruff check` + `ruff format` on commit
- `pytest` on push

CI is a server-side safety net that catches anything that slipped past pre-commit.
