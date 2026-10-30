# Docker Deployment Guide

> Operational notice: this campaign did not deploy. Before any future deployment follow [Operations](OPERATIONS.md), apply the canonical Alembic head, and retain test-mode Stripe settings.

Complete guide for running PatchHive with Docker and Docker Compose for local development and self-hosted production deployment.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [Management Commands](#management-commands)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Prerequisites

### Required Software

1. **Docker** (version 20.10+)
   - [Install Docker Desktop](https://www.docker.com/products/docker-desktop/) (macOS/Windows)
   - [Install Docker Engine](https://docs.docker.com/engine/install/) (Linux)

2. **Docker Compose** (version 2.0+)
   - Included with Docker Desktop
   - Linux: Install separately via package manager

### Verify Installation

```bash
docker --version
# Docker version 24.0.0 or higher

docker compose version
# Docker Compose version v2.20.0 or higher
```

---

## 🚀 Quick Start

Get PatchHive running locally in 3 commands:

```bash
# 1. Clone repository
git clone https://github.com/scrimshawlife-ctrl/Patch-Hive.git
cd Patch-Hive

# 2. Start all services
docker compose up -d

# 3. Open in browser
open http://localhost:5173
```

**That's it!** PatchHive is now running:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Database: localhost:5432

---

## 💻 Development Setup

### Start Development Environment

```bash
# Start all services in foreground (see logs)
docker compose up

# Or start in background (detached mode)
docker compose up -d

# Follow logs
docker compose logs -f

# Follow specific service logs
docker compose logs -f backend
```

### Services Overview

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  Frontend (Vite Dev Server)                    │
│  http://localhost:5173                          │
│  • Hot module reload enabled                    │
│  • Source maps enabled                          │
│                                                 │
└─────────────────────────────────────────────────┘
                      │
                      │ HTTP
                      ▼
┌─────────────────────────────────────────────────┐
│                                                 │
│  Backend (FastAPI + Uvicorn)                   │
│  http://localhost:8000                          │
│  • Auto-reload on code changes                  │
│  • Interactive API docs at /docs                │
│                                                 │
└─────────────────────────────────────────────────┘
                      │
                      │ PostgreSQL
                      ▼
┌─────────────────────────────────────────────────┐
│                                                 │
│  PostgreSQL 15                                  │
│  localhost:5432                                 │
│  • Persistent volume storage                    │
│  • Auto-initialization                          │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Development Workflow

#### Making Code Changes

**Backend changes:**
```bash
# Edit files in backend/
# Uvicorn auto-reloads when you save
```

**Frontend changes:**
```bash
# Edit files in frontend/src/
# Vite hot-reloads automatically
```

#### Running Tests

```bash
# Backend tests
docker compose exec backend pytest

# Frontend tests
docker compose exec frontend-dev npm test

# Backend tests with coverage
docker compose exec backend pytest --cov

# Type checking
docker compose exec frontend-dev npm run type-check
```

#### Database Access

```bash
# Connect to PostgreSQL
docker compose exec db psql -U patchhive -d patchhive

# Run SQL commands
docker compose exec db psql -U patchhive -d patchhive -c "SELECT * FROM modules;"

# Backup database
docker compose exec db pg_dump -U patchhive patchhive > backup.sql

# Restore database
docker compose exec -T db psql -U patchhive -d patchhive < backup.sql
```

#### Rebuild After Dependency Changes

```bash
# Rebuild specific service
docker compose build backend

# Rebuild all services
docker compose build

# Rebuild and restart
docker compose up -d --build
```

### Stop Development Environment

```bash
# Stop services (preserves data)
docker compose stop

# Stop and remove containers (preserves data)
docker compose down

# Stop and remove containers + volumes (deletes data)
docker compose down -v
```

---

## 🏭 Production Deployment

### Step 1: Configure Environment

```bash
# Copy environment template
cp .env.docker .env

# Edit with production values
nano .env
```

**Required values:**
```bash
# Generate strong password
DATABASE_PASSWORD=$(openssl rand -base64 32)

# Generate secret key
SECRET_KEY=$(openssl rand -base64 32)

# Set your domain
CORS_ORIGINS=https://yourdomain.com
VITE_API_URL=https://api.yourdomain.com
```

### Step 2: Deploy with Production Compose

```bash
# Start production stack
docker compose -f docker-compose.prod.yml up -d

# Verify services are running
docker compose -f docker-compose.prod.yml ps

# Check logs
docker compose -f docker-compose.prod.yml logs -f
```

### Step 3: Configure Reverse Proxy (Optional)

For SSL/HTTPS support, use Nginx or Traefik:

#### Option A: Built-in Nginx Proxy

```bash
# Create nginx directory
mkdir -p nginx/ssl

# Add your SSL certificates
cp /path/to/fullchain.pem nginx/ssl/
cp /path/to/privkey.pem nginx/ssl/

# Create nginx config
cat > nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }

    upstream frontend {
        server frontend:80;
    }

    server {
        listen 80;
        server_name yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name yourdomain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # Frontend
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # Backend API
        location /api/ {
            proxy_pass http://backend/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
EOF

# Start with nginx proxy
docker compose -f docker-compose.prod.yml --profile with-proxy up -d
```

#### Option B: External Reverse Proxy (Traefik/Caddy)

Add labels to `docker-compose.prod.yml`:

```yaml
services:
  backend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.patchhive-api.rule=Host(`api.yourdomain.com`)"
      - "traefik.http.services.patchhive-api.loadbalancer.server.port=8000"

  frontend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.patchhive.rule=Host(`yourdomain.com`)"
      - "traefik.http.services.patchhive.loadbalancer.server.port=80"
```

### Step 4: Verify Deployment

```bash
# Check all services are healthy
docker compose -f docker-compose.prod.yml ps

# Test backend API
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# Test frontend
curl -I http://localhost/health
# Expected: HTTP/1.1 200 OK

# Check database tables were created
docker compose -f docker-compose.prod.yml exec db psql -U patchhive -d patchhive -c "\dt"
```

---

## ⚙️ Configuration

### Environment Variables

#### Backend Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | postgresql://... | Yes |
| `SECRET_KEY` | JWT signing key | - | Yes |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | * | Yes |
| `APP_NAME` | Application name | PatchHive | No |
| `APP_VERSION` | Application version | 1.0.0 | No |
| `ABX_CORE_VERSION` | ABX-Core compliance version | 1.2 | No |
| `ENFORCE_SEED_TRACEABILITY` | Enforce SEED provenance | true | No |
| `RUN_MIGRATIONS` | Run DB migrations on startup; only `true` or `1` enable it (local compose opts in; Cloudflare Workers do not, use the db-migrate workflow) | false | No |

#### Frontend Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `VITE_API_URL` | Backend API URL | http://localhost:8000 | Yes |

#### Database Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `POSTGRES_USER` | PostgreSQL username | patchhive | No |
| `POSTGRES_PASSWORD` | PostgreSQL password | - | Yes |
| `POSTGRES_DB` | Database name | patchhive | No |

### Volume Mounts

Development mounts (hot-reload):
```yaml
volumes:
  - ./backend:/app              # Backend source code
  - ./frontend:/app             # Frontend source code
  - postgres_data:/var/lib/postgresql/data  # Database data
```

Production mounts (minimal):
```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data  # Database data only
  - ./backups:/backups          # Database backups
```

### Port Mappings

| Service | Container Port | Host Port | Purpose |
|---------|----------------|-----------|---------|
| Frontend (Dev) | 5173 | 5173 | Vite dev server |
| Frontend (Prod) | 80 | 80 | Nginx static server |
| Backend | 8000 | 8000 | FastAPI application |
| Database | 5432 | 5432 | PostgreSQL |
| Nginx (Optional) | 443 | 443 | HTTPS reverse proxy |

---

## 🔧 Management Commands

### Container Management

```bash
# View running containers
docker compose ps

# View all containers (including stopped)
docker compose ps -a

# Start services
docker compose start

# Stop services
docker compose stop

# Restart services
docker compose restart

# Restart specific service
docker compose restart backend

# Remove stopped containers
docker compose rm

# Scale a service
docker compose up -d --scale backend=3
```

### Logs and Monitoring

```bash
# View logs for all services
docker compose logs

# Follow logs in real-time
docker compose logs -f

# View logs for specific service
docker compose logs backend

# View last 100 lines
docker compose logs --tail=100

# View logs with timestamps
docker compose logs -f --timestamps
```

### Shell Access

```bash
# Access backend shell
docker compose exec backend bash

# Access database shell
docker compose exec db psql -U patchhive -d patchhive

# Run Python shell in backend
docker compose exec backend python

# Access frontend shell
docker compose exec frontend-dev sh

# Run command in backend
docker compose exec backend python -m pytest
```

### Database Management

```bash
# Backup database
docker compose exec db pg_dump -U patchhive patchhive > "backup_$(date +%Y%m%d_%H%M%S).sql"

# Restore database
docker compose exec -T db psql -U patchhive -d patchhive < backup.sql

# Reset database (WARNING: Deletes all data!)
docker compose down -v
docker compose up -d

# View database size
docker compose exec db psql -U patchhive -d patchhive -c "SELECT pg_size_pretty(pg_database_size('patchhive'));"

# View table sizes
docker compose exec db psql -U patchhive -d patchhive -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

### Cleanup

```bash
# Remove stopped containers
docker compose down

# Remove containers and networks
docker compose down --remove-orphans

# Remove containers, networks, and volumes (DELETES DATA!)
docker compose down -v

# Remove containers, networks, volumes, and images
docker compose down -v --rmi all

# Clean up Docker system
docker system prune -a
```

---

## 🐛 Troubleshooting

### Issue: Containers won't start

**Check logs:**
```bash
docker compose logs
```

**Common causes:**
1. Port already in use
2. Missing environment variables
3. Insufficient disk space

**Solutions:**
```bash
# Check port conflicts
lsof -i :8000
lsof -i :5173
lsof -i :5432

# Stop conflicting services
docker compose down

# Check disk space
df -h

# Clean up Docker resources
docker system prune -a
```

### Issue: Database connection fails

**Verify database is running:**
```bash
docker compose ps db
docker compose logs db
```

**Test connection:**
```bash
docker compose exec db pg_isready -U patchhive
```

**Check environment variables:**
```bash
docker compose exec backend env | grep DATABASE
```

**Wait for database to be ready:**
```bash
# Database needs 10-30 seconds to initialize on first run
docker compose logs -f db
# Wait for: "database system is ready to accept connections"
```

### Issue: Hot reload not working

**Backend:**
```bash
# Ensure volume is mounted correctly
docker compose exec backend ls -la /app

# Restart with rebuild
docker compose up -d --build backend
```

**Frontend:**
```bash
# Ensure node_modules is in volume
docker compose exec frontend-dev ls -la /app/node_modules

# Reinstall dependencies
docker compose exec frontend-dev npm install

# Clear cache and restart
docker compose restart frontend-dev
```

### Issue: "Permission denied" errors

**Fix file permissions:**
```bash
# Linux: Fix ownership
sudo chown -R $USER:$USER .

# Or run containers as your user
docker compose run --user $(id -u):$(id -g) backend bash
```

### Issue: Out of disk space

**Check Docker disk usage:**
```bash
docker system df

# Clean up
docker system prune -a --volumes
```

### Issue: Slow builds

**Use BuildKit:**
```bash
# Enable BuildKit (faster builds)
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Rebuild
docker compose build
```

**Use cache:**
```bash
# Rebuild without cache
docker compose build --no-cache

# Pull cached layers
docker compose pull
```

---

## 📊 Resource Usage

### Default Resource Limits

No limits set by default. Containers can use all available resources.

### Set Resource Limits

Edit `docker-compose.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### Monitor Resource Usage

```bash
# Real-time resource usage
docker stats

# View specific container
docker stats patchhive-backend
```

---

## 🔒 Security Best Practices

### Production Security Checklist

- [ ] Change default passwords
- [ ] Use strong SECRET_KEY (32+ chars)
- [ ] Enable SSL/HTTPS
- [ ] Restrict database access (remove port mapping)
- [ ] Use secrets management (Docker Secrets or HashiCorp Vault)
- [ ] Enable database backups
- [ ] Set resource limits
- [ ] Use non-root user in containers
- [ ] Scan images for vulnerabilities
- [ ] Keep images updated

### Secure Database Access

Remove database port mapping in production:

```yaml
services:
  db:
    # ports:
    #   - "5432:5432"  # Comment out or remove
```

Backend can still access via Docker network.

### Use Docker Secrets (Swarm/Kubernetes)

```yaml
services:
  backend:
    secrets:
      - db_password
      - secret_key

secrets:
  db_password:
    external: true
  secret_key:
    external: true
```

---

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [FastAPI Docker Deployment](https://fastapi.tiangolo.com/deployment/docker/)
- [PostgreSQL Docker Image](https://hub.docker.com/_/postgres)

---

**Ready to deploy!** 🚀

For cloud deployments, see:
- [Azure Deployment](AZURE_DEPLOYMENT.md)
- [Render Deployment](RENDER_DEPLOYMENT.md)
