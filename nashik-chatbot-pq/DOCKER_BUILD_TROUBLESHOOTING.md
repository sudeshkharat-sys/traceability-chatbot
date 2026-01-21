# Docker Build Troubleshooting Guide

## Issue: Build Failing at npm install

Your logs show the build stops at step 9/23 during `npm install --legacy-peer-deps`.

## Root Cause

Node 24.13 is very new (released recently) and may have issues with:
- Alpine Linux compatibility
- npm package resolution
- Memory usage during build

## Solution Applied

Changed Dockerfile from:
```dockerfile
FROM node:24.13-alpine AS frontend-builder
```

To:
```dockerfile
FROM node:20-alpine AS frontend-builder
```

**Why Node 20?**
- ✅ LTS (Long Term Support) - Stable and well-tested
- ✅ Better Alpine Linux compatibility
- ✅ Works with React 19
- ✅ Lower memory usage during builds
- ✅ Mature ecosystem

## Steps to Fix on Your VM

### 1. Pull Latest Changes

```bash
cd ~/nashik-chatbot-pq
git pull origin claude/docker-setup-postgres-neo4j-GJI8n
```

### 2. Clean Previous Failed Build

```bash
# Stop any running containers
sudo docker compose down

# Remove failed build containers
sudo docker compose rm -f app

# Clean build cache (IMPORTANT!)
sudo docker builder prune -af

# Or more aggressive cleanup
sudo docker system prune -af
```

### 3. Rebuild with Node 20

```bash
# Build with no cache to ensure clean build
sudo docker compose build --no-cache app

# Or rebuild everything
sudo docker compose up -d --build --force-recreate
```

### 4. Monitor Build Progress

```bash
# Watch build logs in real-time
sudo docker compose up --build

# Or build and see progress
sudo docker compose build app
```

## Diagnostic Commands

### Check What Failed

```bash
# See all containers (including stopped)
sudo docker compose ps -a

# Get last 200 lines of logs
sudo docker compose logs --tail=200

# Check specific app logs
sudo docker compose logs app
```

### Check Docker Resources

```bash
# Check disk space
df -h

# Check Docker disk usage
sudo docker system df

# Check memory
free -h
```

### Verify Build Success

```bash
# After successful build, check containers
sudo docker compose ps

# Should see 4 healthy containers:
# - traceability-postgres (healthy)
# - traceability-neo4j (healthy)
# - traceability-app (healthy)
# - traceability-nginx (healthy)
```

## Common Build Errors and Fixes

### Error 1: npm install hangs or times out

**Symptoms:**
- Build stops at npm install
- No progress for 5+ minutes
- Memory issues

**Fix:**
```dockerfile
# Already applied - using Node 20 LTS instead of 24.13
FROM node:20-alpine AS frontend-builder
```

### Error 2: Out of memory

**Symptoms:**
```
ERROR: Could not build wheels for X which is required to install pyproject.toml-based projects
Killed
```

**Fix:**
```bash
# Increase Docker memory limit
# Edit /etc/docker/daemon.json
sudo nano /etc/docker/daemon.json

# Add:
{
  "default-runtime": "runc",
  "storage-driver": "overlay2"
}

# Restart Docker
sudo systemctl restart docker
```

### Error 3: Python dependencies failing

**Symptoms:**
```
ERROR: Could not find a version that satisfies the requirement X
```

**Fix:**
```bash
# Update pip in Dockerfile (already done)
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
```

### Error 4: Frontend build failing

**Symptoms:**
```
npm ERR! code ELIFECYCLE
npm ERR! errno 1
```

**Fix:**
```bash
# Check if frontend builds locally first
cd frontend
npm install --legacy-peer-deps
npm run build

# If works locally, issue is Docker-specific
```

## If Build Still Fails

### Get Complete Error Logs

```bash
# Build without detached mode to see full output
sudo docker compose up --build

# Save to file
sudo docker compose build app 2>&1 | tee build_full.log

# Share the build_full.log file
```

### Check Node Version Compatibility

```bash
# Test with standard node (not alpine)
# Edit Dockerfile line 5:
FROM node:20 AS frontend-builder  # Remove -alpine

# Rebuild
sudo docker compose build --no-cache app
```

### Try Sequential Build

Instead of multi-stage, try building frontend separately:

```bash
# Build frontend locally first
cd frontend
npm install --legacy-peer-deps
npm run build
cd ..

# Then build Docker (skips frontend build)
sudo docker compose build app
```

## Expected Build Time

- **npm install**: 2-3 minutes
- **npm run build**: 1-2 minutes
- **Python install**: 2-3 minutes
- **Total**: 5-10 minutes for first build

If npm install takes > 5 minutes, it's likely hung.

## Verification After Successful Build

```bash
# 1. All containers running
sudo docker compose ps
# Should show 4 containers, all "Up" and "healthy"

# 2. Frontend built
sudo docker compose exec app ls -la frontend/build/
# Should show index.html and static/ directory

# 3. App accessible
curl http://localhost:7434
# Should return HTML

# 4. Check logs for errors
sudo docker compose logs app | grep -i error
# Should be minimal/no errors
```

## Prevention for Future

### Use Stable Node Versions

```dockerfile
# Good: LTS versions
FROM node:18-alpine  # LTS until April 2025
FROM node:20-alpine  # LTS until April 2026 ✅ Current
FROM node:22-alpine  # LTS until April 2027

# Avoid: Bleeding edge
FROM node:24-alpine  # Too new, may have issues
```

### Lock Node Version in package.json

```json
{
  "engines": {
    "node": ">=18.0.0 <21.0.0"
  }
}
```

### Use Docker BuildKit

```bash
# Enable BuildKit for better caching and performance
export DOCKER_BUILDKIT=1

# Or in docker-compose.yml
COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 docker compose build
```

## Summary

**Problem**: Node 24.13 too new, Alpine Linux issues, npm install hangs

**Solution**: Use Node 20 LTS (stable, tested, compatible)

**Steps**:
1. Pull latest code
2. Clean Docker cache: `sudo docker builder prune -af`
3. Rebuild: `sudo docker compose up -d --build --force-recreate`
4. Verify: `sudo docker compose ps` shows all healthy

## Need More Help?

If build still fails, share:
1. Complete build output: `sudo docker compose build app 2>&1 | tee build.log`
2. System info: `docker version`, `docker compose version`, `free -h`, `df -h`
3. Error message (exact line where it fails)
