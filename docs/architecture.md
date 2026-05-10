# Architecture Design

## Overview

A lightweight web service designed for a small team (≤5 users), built on AWS with a focus on simplicity and maintainability. The system handles real-time data display via API, scheduled batch jobs, S3 storage, Telegram bot automation, and is designed to accommodate custom AI agents in the future.

---

## Requirements

| Category | Details |
|----------|---------|
| Users | ≤ 5 people |
| Deployment | Web-accessible |
| Auth | Possible (login feature) |
| Data | Dashboard display, external API ingestion |
| Scheduling | Daily batch jobs |
| Storage | S3 (crawled data), PostgreSQL (structured data) |
| Messaging | Telegram bot |
| Infrastructure | AWS-based, always-on server |

---

## Technology Stack

### Frontend

| Tool | Role |
|------|------|
| React | UI components, dashboard, data visualization |
| Vite | Dev server, production build tooling |

**Dev:**
```bash
npm run dev
```

**Build:**
```bash
npm run build
# Output: dist/
```

Nginx serves the `dist/` static files in production.

---

### Backend

| Tool | Role |
|------|------|
| FastAPI | REST API server, login handling, data queries |
| Gunicorn + UvicornWorker | Production ASGI server |

**Dev:**
```bash
uvicorn app.main:app --reload
```

**Production:**
```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker
```

---

### Database

**PostgreSQL** running as a Docker container on EC2.

- Stores user info, service data, and metadata
- Data persisted via Docker named volume (survives container restarts)
- Chosen over AWS RDS to reduce cost for small-scale usage

---

### Batch / Scheduler

**cron** running inside the EC2 host or a dedicated container.

Example crontab entry:
```cron
0 3 * * * docker exec backend python batch/collect.py
```

Responsibilities:
- Crawl external data sources on a schedule
- Store results in S3
- Trigger Telegram notifications

---

### Telegram Bot

A long-running Python process managed as a Docker service.

- Responds to slash commands (e.g., `/status`, `/report`)
- Sends scheduled messages to designated Telegram channels
- Runs continuously alongside FastAPI

---

### Storage

**AWS S3** — used for storing crawled/batch data.

- FastAPI and batch scripts read/write directly via `boto3`
- Not used as a web host; purely as object storage

---

## Infrastructure

### AWS Resources

| Resource | Spec | Purpose |
|----------|------|---------|
| EC2 | t3.medium (4GB RAM) | Runs all Docker services |
| S3 | Standard | Batch data storage |

RDS is intentionally excluded — PostgreSQL runs as a Docker container on EC2, which is sufficient for this scale.

---

## System Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────────┐
│             EC2 t3.medium           │
│                                     │
│  ┌──────────────────────────────┐   │
│  │         Nginx (port 80/443)  │   │
│  │  /          → React (dist/)  │   │
│  │  /api/*     → FastAPI proxy  │   │
│  └──────────────────────────────┘   │
│              │                      │
│              ▼                      │
│  ┌──────────────────────────────┐   │
│  │           FastAPI            │   │
│  └──────────────────────────────┘   │
│       │              │              │
│       ▼              ▼              │
│  ┌─────────┐   ┌───────────┐       │
│  │ PostgreSQL│  │    S3     │       │
│  │(Docker) │   │  (AWS)    │       │
│  └─────────┘   └───────────┘       │
│                                     │
│  ┌──────────────────────────────┐   │
│  │       Telegram Bot           │   │
│  │    (long-running service)    │   │
│  └──────────────────────────────┘   │
│                                     │
│  ┌──────────────────────────────┐   │
│  │     cron (batch jobs)        │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

---

## Deployment Pipeline

### Strategy: GitHub Actions (CI/CD)

On every push to `main`, GitHub Actions automatically SSHs into EC2 and redeploys the stack.

```
Local: git push origin main
    │
    ▼
GitHub detects push to main
    │
    ▼
GitHub Actions Runner
    │  SSH
    ▼
EC2: git pull → docker compose up -d --build
```

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to EC2
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USER }}
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /app
            git pull origin main
            docker compose up -d --build
```

### Required GitHub Secrets

| Secret | Value |
|--------|-------|
| `EC2_HOST` | EC2 public IP |
| `EC2_USER` | `ec2-user` or `ubuntu` |
| `EC2_SSH_KEY` | Private SSH key (PEM) |

### EC2 Initial Setup (one-time)

```bash
# On EC2: install Docker, git, then clone repo
git clone https://github.com/your-org/your-repo.git /app
cd /app
docker compose up -d --build
# After this, GitHub Actions handles all future deploys
```

---

## Docker Compose Structure

All services are managed via Docker Compose on a single EC2 instance.

```yaml
# docker-compose.yml (conceptual structure)
services:
  nginx:
    # Serves React static files
    # Proxies /api/* to FastAPI
    ports: ["80:80", "443:443"]

  fastapi:
    # REST API + business logic
    # Communicates with postgres and S3

  postgres:
    # PostgreSQL database
    volumes:
      - postgres_data:/var/lib/postgresql/data

  telegram-bot:
    # Long-running bot process
    restart: always

volumes:
  postgres_data:
```

---

## Project Structure

```
project/
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD pipeline
├── frontend/                   # React + Vite
│   ├── src/
│   ├── index.html
│   └── vite.config.js
├── backend/                    # FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   └── models/
│   ├── batch/                  # Cron job scripts
│   │   └── collect.py
│   └── bot/                    # Telegram bot
│       └── main.py
├── nginx/
│   └── nginx.conf
├── docs/
│   └── architecture.md         # This document
└── docker-compose.yml
```

---

## Future Considerations

- **Custom AI Agents**: The architecture is designed to accommodate future Claude-style custom agents. These can be added as additional Docker services sharing the same internal network and PostgreSQL/S3 access.
- **HTTPS**: Add Certbot (Let's Encrypt) as an Nginx companion container when a domain is configured.
- **Auth**: JWT-based authentication via FastAPI is straightforward to add when needed.
