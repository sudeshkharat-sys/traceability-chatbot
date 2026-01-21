# Environment Configuration Guide

This guide explains how environment variables and configuration files work in this project.

## Overview

The project uses a single `.env` file for configuration that works for both Docker and local development.

**Simple Setup:**
1. Copy `.env.example` to `.env`
2. Fill in your credentials
3. For local dev, change `POSTGRES_HOST` and `NEO4J_URL` to localhost values

## File Structure

```
/
├── .env.example                # Template (commit to git)
├── .env                        # Your config (DO NOT COMMIT - gitignored)
├── docker-compose.yml          # Reads from .env
└── app/config/
    └── config.py              # Reads environment variables
```

## Docker Deployment Setup

### Step 1: Create Your .env File

```bash
# Copy the example file
cp .env.example .env

# Edit with your credentials
nano .env  # or use your preferred editor
```

### Step 2: Update Required Values

**REQUIRED - You must change these:**
```env
AZURE_API_KEY=your_actual_azure_api_key_here
AZURE_CHAT_ENDPOINT=https://your-resource.openai.azure.com/...
AZURE_EMBEDDING_ENDPOINT=https://your-resource.openai.azure.com/...
```

**SECURITY - Change default passwords:**
```env
POSTGRES_PASSWORD=your_secure_postgres_password
NEO4J_PASSWORD=your_secure_neo4j_password
SESSION_SECRET=your_random_session_secret_key
```

### Step 3: Start Services

```bash
docker-compose up -d
```

### How It Works

1. **docker-compose.yml reads .env file** - Variables are automatically loaded
2. **Environment variables passed to containers** - Using `${VAR_NAME}` syntax
3. **.env mounted into app container** - Available at `/app/app/config/.env`
4. **Application reads from environment** - Pydantic Settings loads variables

```
┌─────────────┐
│   .env      │ (Root directory)
└──────┬──────┘
       │
       ├──────────────────────────────┐
       │                              │
       ▼                              ▼
┌─────────────────┐          ┌─────────────────┐
│ docker-compose  │          │ app container   │
│                 │          │                 │
│ Uses ${VAR}     │────────> │ Receives env    │
│ syntax          │          │ variables       │
└─────────────────┘          └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │  config.py      │
                             │  Reads from env │
                             └─────────────────┘
```

## Local Development Setup

### Step 1: Create .env File

```bash
# Copy the same example file
cp .env.example .env

# Edit with your credentials
nano .env
```

### Step 2: Update for Local Services

Change these values in your `.env` file:

```env
# Change from Docker service names to localhost
POSTGRES_HOST=localhost           # Instead of 'postgres'
NEO4J_URL=neo4j://127.0.0.1:7687  # Instead of 'neo4j://neo4j:7687'
```

### Step 3: Run Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

> **Note:** The same `.env` file works for both Docker and local development. Just change the host values for local dev.

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_API_KEY` | Azure OpenAI API Key | `abc123...` |
| `AZURE_CHAT_ENDPOINT` | Chat model endpoint | `https://...` |
| `AZURE_EMBEDDING_ENDPOINT` | Embedding endpoint | `https://...` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `secure_pass` |
| `NEO4J_PASSWORD` | Neo4j password | `secure_pass` |

### Optional Variables (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `postgres` | PostgreSQL username |
| `POSTGRES_DB` | `chatbot` | Database name |
| `POSTGRES_HOST` | `postgres` (Docker) / `localhost` (Local) | Database host |
| `NEO4J_USERNAME` | `neo4j` | Neo4j username |
| `NEO4J_URL` | `neo4j://neo4j:7687` | Neo4j connection URL |
| `SERVER_HOST` | `0.0.0.0` | Application host |
| `SERVER_PORT` | `5000` | Application port |
| `SESSION_SECRET` | `change-me-in-production` | Session encryption key |

## Security Best Practices

### ✅ DO

- ✅ Copy `.env.example` to `.env` and fill in actual values
- ✅ Change ALL default passwords before production deployment
- ✅ Keep `.env` files in `.gitignore` (already configured)
- ✅ Use strong, unique passwords for each service
- ✅ Use environment-specific values (different for dev/staging/prod)
- ✅ Rotate credentials regularly

### ❌ DON'T

- ❌ Commit `.env` files to git (contains secrets!)
- ❌ Use default passwords in production
- ❌ Share `.env` files via email or chat
- ❌ Hardcode passwords in `docker-compose.yml`
- ❌ Reuse passwords across services
- ❌ Leave test credentials in production

## Verification

### Check Docker Compose Reads .env

```bash
# View environment variables that will be used
docker-compose config | grep -A 5 "environment:"
```

### Verify Variables in Container

```bash
# Enter the app container
docker-compose exec app bash

# Check environment variables
env | grep -E 'NEO4J|POSTGRES|AZURE'

# Exit container
exit
```

### Test Configuration Loading

```bash
# Inside app container
docker-compose exec app python -c "
from app.config.config import get_settings
settings = get_settings()
print(f'Neo4j URL: {settings.NEO4J_URL}')
print(f'Postgres Host: {settings.POSTGRES_HOST}')
"
```

## Troubleshooting

### Issue: Variables Not Loading

**Symptom:** Application can't find environment variables

**Solutions:**
1. Check `.env` file exists in root directory: `ls -la .env`
2. Verify `.env` file has correct syntax (no spaces around `=`)
3. Restart Docker Compose: `docker-compose down && docker-compose up -d`
4. Check if `.env` is mounted: `docker-compose exec app cat /app/app/config/.env`

### Issue: Permission Denied

**Symptom:** Can't read `.env` file in container

**Solutions:**
```bash
# Fix file permissions
chmod 644 .env

# Restart containers
docker-compose restart app
```

### Issue: Wrong Database Host

**Symptom:** Can't connect to databases

**Solutions:**
```bash
# For Docker, use service names:
NEO4J_URL=neo4j://neo4j:7687
POSTGRES_HOST=postgres

# For local development, use localhost:
NEO4J_URL=neo4j://127.0.0.1:7687
POSTGRES_HOST=localhost
```

## Migration from Old Setup

If you have existing configuration:

### From Hardcoded docker-compose.yml

```bash
# 1. Create .env file
cp .env.example .env

# 2. Move hardcoded passwords to .env
# OLD (docker-compose.yml):
#   POSTGRES_PASSWORD: password
# NEW (.env):
#   POSTGRES_PASSWORD=your_secure_password

# 3. Update docker-compose.yml to use variables
# Already done in current version

# 4. Restart services
docker-compose down
docker-compose up -d
```

### Upgrading from Previous Setup

If you previously had separate `.env` files:

```bash
# The project now uses a single .env file
# 1. All configuration is in root .env
# 2. No separate app/config/.env needed
# 3. Simply restart: docker-compose down && docker-compose up -d
```

## Summary

### For Docker (Recommended)

```bash
# One-time setup
cp .env.example .env
nano .env  # Fill in credentials

# Start services
docker-compose up -d
```

### For Local Development

```bash
# One-time setup (same file as Docker!)
cp .env.example .env
nano .env  # Fill in credentials and change hosts to localhost

# Run app
python main.py
```

## Quick Reference

```bash
# Docker Deployment
.env.example → .env → docker-compose.yml → containers

# Local Development
.env.example → .env → config.py → app

# Check current config
docker-compose config

# Verify variables
docker-compose exec app env | grep NEO4J

# Restart with new variables
docker-compose restart app
```

## Additional Resources

- [Docker Compose Environment Variables](https://docs.docker.com/compose/environment-variables/)
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [12-Factor App: Config](https://12factor.net/config)
