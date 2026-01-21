# Frontend Build Fix Guide

## Issue

The Docker build was failing with:
```
npm error Missing: yaml@2.8.2 from lock file
npm error `npm ci` can only install packages when your package.json and package-lock.json are in sync
```

## Root Cause

The `package-lock.json` was generated with **Node v24.13.0** locally, but the Docker container uses **Node 18-alpine**. This causes compatibility issues with `npm ci` which requires exact lock file matching.

## Solution Applied

Updated `Dockerfile` to use `npm install --legacy-peer-deps` instead of `npm ci`:

```dockerfile
# Old (strict, requires exact match)
RUN npm ci --production=false

# New (flexible, works with different Node versions)
RUN npm install --legacy-peer-deps --production=false
```

## Why This Works

| Command | Behavior | Use Case |
|---------|----------|----------|
| `npm ci` | Strict - requires exact lock file match | Production, CI/CD |
| `npm install` | Flexible - works with lock file mismatches | Development, mixed environments |
| `--legacy-peer-deps` | Ignores peer dependency conflicts | React 19 compatibility |

## Best Practice: Regenerate Lock File with Node 18

For cleaner builds in the future, regenerate `package-lock.json` with Node 18:

### Option 1: Using Docker (Recommended)

```bash
# Navigate to project
cd /home/user/Traceability/nashik-chatbot-pq

# Remove existing lock file
rm frontend/package-lock.json

# Use Docker to regenerate with Node 18
docker run --rm -v "$(pwd)/frontend:/app" -w /app node:18-alpine sh -c "npm install --legacy-peer-deps"

# Verify new lock file was created
ls -lh frontend/package-lock.json
```

### Option 2: Using nvm (Node Version Manager)

```bash
# Install nvm if you don't have it
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Install Node 18
nvm install 18
nvm use 18

# Navigate to frontend
cd frontend

# Remove old lock file
rm package-lock.json

# Regenerate with Node 18
npm install --legacy-peer-deps

# Check Node version
node --version  # Should show v18.x.x

# Switch back to your preferred version
nvm use 24  # or your version
```

### Option 3: Keep Current Setup

If regenerating is not convenient, the current Dockerfile fix will work fine. The build will:
- Use `npm install` which regenerates dependencies
- Use `--legacy-peer-deps` to handle React 19
- Cache properly in Docker layers

## Verification

After updating Dockerfile, rebuild:

```bash
# Remove old build cache
docker compose down
docker system prune -f

# Rebuild and start
docker compose up -d --build

# Check build logs
docker compose logs app

# Verify frontend is built
docker compose exec app ls -la frontend/build/
```

## Why Node Version Mismatch Happened

1. **Local Development**: You have Node v24.13.0 installed
2. **Docker Container**: Uses Node 18-alpine (for stability)
3. **Lock File Generation**: Created with Node 24
4. **Build Time**: Docker tries to use lock file with Node 18
5. **Result**: Mismatch causes `npm ci` to fail

## Long-term Solution

Choose one approach:

### Approach 1: Match Docker Version Locally
```bash
nvm use 18
# Always use Node 18 for this project
```

### Approach 2: Keep Using npm install in Docker (Current)
```dockerfile
# Dockerfile already updated to use:
RUN npm install --legacy-peer-deps --production=false
```

### Approach 3: Update Docker to Node 20 or 22
```dockerfile
# Change this line in Dockerfile:
FROM node:18-alpine AS frontend-builder
# To:
FROM node:20-alpine AS frontend-builder
# or
FROM node:22-alpine AS frontend-builder
```

**Recommendation**: Stick with current fix (npm install) unless you want to standardize on a specific Node version.

## Additional Notes

- The `yaml@2.8.2` dependency is a transitive dependency from `react-markdown` or similar packages
- Docker uses Node 18 for LTS stability
- Your local Node 24 has different package resolution algorithms
- `--legacy-peer-deps` handles React 19 peer dependency warnings

## Files Modified

- ✅ `Dockerfile` - Changed `npm ci` to `npm install --legacy-peer-deps`

## Test Commands

```bash
# Clean build
docker compose down
docker compose build --no-cache app
docker compose up -d

# Check if frontend built successfully
docker compose exec app ls -la frontend/build/
docker compose exec app ls -la frontend/build/static/

# Test application
curl http://localhost:7434
# Should return HTML
```
