# Infrastructure Setup Guide

Complete step-by-step record of the infrastructure setup for BicQuant.

---

## Table of Contents

1. [IAM User](#1-iam-user)
2. [EC2 Instance](#2-ec2-instance)
3. [EC2 Initial Setup](#3-ec2-initial-setup)
4. [GitHub SSH Key (EC2 → GitHub)](#4-github-ssh-key-ec2--github)
5. [GitHub Actions Deploy Key (GitHub → EC2)](#5-github-actions-deploy-key-github--ec2)
6. [GitHub Actions Workflow](#6-github-actions-workflow)
7. [Security Group](#7-security-group)
8. [Project Deployment](#8-project-deployment)
9. [Environment Variables](#9-environment-variables)
10. [Docker Compose](#10-docker-compose)

---

## 1. IAM User

**Why**: Never use the root account for day-to-day operations.

- Using existing IAM user: `e*******a`
- Group: `admin` (AdministratorAccess policy attached)
- Login URL: `https://<account-id>.signin.aws.amazon.com/console`

> **Note**: MFA is not yet configured on this user. Recommended to set up when time allows.

---

## 2. EC2 Instance

**Console**: EC2 → Launch instance

| Setting | Value |
|---------|-------|
| Name | `bicquant` |
| AMI | Ubuntu Server 24.04 LTS |
| Instance type | `t3.medium` (4GB RAM) |
| Key pair | `bicquant-key` (RSA, `.pem`) |
| Storage | 20GB |

**Key pair file location (local)**:
```
/path/to/bicquant-key.pem
```

**Public IP**: `***.***.***.***`

### SSH Access

```bash
# Set correct permissions (required — SSH will reject without this)
chmod 400 /path/to/bicquant-key.pem

# Connect
ssh -i /path/to/bicquant-key.pem ubuntu@<EC2_PUBLIC_IP>
```

---

## 3. EC2 Initial Setup

Run on the EC2 server after first SSH login.

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Docker (via official Docker repository)
# Reference: https://docs.docker.com/engine/install/ubuntu/
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start Docker and enable on boot
sudo systemctl enable --now docker

# Allow ubuntu user to run Docker without sudo
sudo usermod -aG docker ubuntu

# Re-login to apply group change
exit
# ssh back in, then verify:
docker run hello-world
docker compose version

# Install git
sudo apt install -y git
```

---

## 4. GitHub SSH Key (EC2 → GitHub)

Allows the EC2 server to `git pull` from the private GitHub repository.

### On EC2

```bash
# Generate deploy key
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N ""

# Print public key — copy this
cat ~/.ssh/github_deploy.pub

# Configure SSH to use this key for GitHub
cat >> ~/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_deploy
EOF
```

### On GitHub

Repository → **Settings** → **Deploy keys** → **Add deploy key**

| Field | Value |
|-------|-------|
| Title | `bicquant-ec2` |
| Key | (paste public key output above) |
| Allow write access | unchecked |

### Test connection

```bash
ssh -T git@github.com -i ~/.ssh/github_deploy
# Expected: "Hi username! You've successfully authenticated..."
```

### Clone repository

```bash
sudo mkdir /app
sudo chown ubuntu:ubuntu /app
git clone git@github.com:<github-username>/bicquant.git /app
```

---

## 5. GitHub Actions Deploy Key (GitHub → EC2)

Allows GitHub Actions to SSH into EC2 and trigger deployments.

### On EC2

```bash
# Generate deploy key
ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""

# Register public key so EC2 accepts connections with this key
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys

# Print private key — copy everything including header/footer lines
cat ~/.ssh/deploy_key
```

### On GitHub

Repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret name | Value |
|-------------|-------|
| `EC2_HOST` | `***.***.***.***` |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | (paste full private key including `-----BEGIN/END OPENSSH PRIVATE KEY-----`) |

---

## 6. GitHub Actions Workflow

File: `.github/workflows/deploy.yml`

```yaml
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

**Trigger**: Every push to `main` branch automatically deploys to EC2.

`appleboy/ssh-action@v1` is an open-source GitHub Action that handles the SSH connection and remote command execution.

---

## 7. Security Group

EC2 Console → Instance → **Security** tab → Security group → **Edit inbound rules**

| Rule | Type | Protocol | Port | Source |
|------|------|----------|------|--------|
| SSH access | SSH | TCP | 22 | `0.0.0.0/0` |
| Web traffic | HTTP | TCP | 80 | `0.0.0.0/0` |

> HTTPS (port 443) will be added when a domain and SSL certificate are configured.

---

## 8. Project Deployment

### Initial deploy (one-time on EC2)

```bash
cd /app
cp .env.example .env
nano .env          # fill in actual secret values
docker compose up -d --build
```

### Subsequent deploys

Handled automatically by GitHub Actions on every push to `main`.

To deploy manually:

```bash
cd /app
git pull origin main
docker compose up -d --build
```

### Verify services

```bash
docker compose ps
docker compose logs frontend
docker compose logs backend
```

### Access

```
http://<EC2_PUBLIC_IP>
```

---

## 9. Environment Variables

File: `.env` (gitignored — must be created manually on each server)

```env
# LS Securities Open API
LS_OPENAPI_APP_KEY=
LS_OPENAPI_APP_SECRET=
LS_OPENAPI_USER_ID=

# Telegram
TELEGRAM_BOT_TOKEN=

# Anthropic
ANTHROPIC_API_KEY=

# PostgreSQL
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
DATABASE_URL=  # postgresql://<user>:<password>@postgres:5432/<db>

# FRED API
FRED_API_KEY=
```

---

## 10. Docker Compose

File: `docker-compose.yml`

```yaml
services:
  frontend:
    build: ./frontend        # React (Vite) + nginx — serves UI and proxies /api/*
    ports:
      - "80:80"
    depends_on:
      - backend

  backend:
    build: ./backend         # FastAPI — REST API
    env_file: .env
    expose:
      - "8000"
    depends_on:
      - postgres

  postgres:
    image: postgres:16-alpine
    env_file: .env
    volumes:
      - postgres_data:/var/lib/postgresql/data
    expose:
      - "5432"

  telegram-bot:
    build: ./backend
    command: python -m bot.main   # runs the Telegram bot process
    env_file: .env
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  postgres_data:
```

### Request flow

```
Browser
  ↓ HTTP :80
frontend (nginx)
  ├── /          → serves React static files (dist/)
  └── /api/*     → proxy_pass http://backend:8000
                       ↓
                   FastAPI
                       ├── PostgreSQL (postgres:5432)
                       └── LS Securities Open API (external)
```

### Frontend build (multi-stage Dockerfile)

```dockerfile
# Stage 1: build React app
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: serve with nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

### Backend Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```
