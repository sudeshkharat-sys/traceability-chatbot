# Port 80 Conflict - Quick Fix Guide

## Issue
Port 80 is already in use by another service on your Ubuntu VM.

## Error Message
```
Error: bind: address already in use
Cannot start service nginx: Ports are not available
```

## Solution Applied
Changed external port from **80** to **8080**.

### Updated docker-compose.yml:
```yaml
nginx:
  ports:
    - "8080:80"  # External: 8080, Internal: 80
```

## Access Your Application

| Service | URL |
|---------|-----|
| **Main Application** | `http://your-vm-ip:8080` |
| Direct App (bypass Nginx) | `http://your-vm-ip:5000` |
| Neo4j Browser | `http://your-vm-ip:7474` |
| PostgreSQL | `your-vm-ip:5432` |

## Steps to Apply

```bash
# 1. Pull latest changes
cd ~/nashik-chatbot-pq
git pull origin claude/docker-setup-postgres-neo4j-GJI8n

# 2. Update your .env file to match .env.example
nano .env
# Make sure CORS_ORIGINS includes: http://localhost:8080

# 3. Restart Docker services
sudo docker compose down
sudo docker compose up -d

# 4. Access application
# From browser: http://your-vm-ip:8080
```

## Diagnostic: What's Using Port 80?

```bash
# Check what's using port 80
sudo lsof -i :80

# Or use netstat
sudo netstat -tulpn | grep :80

# Common services that use port 80:
# - Apache2 (httpd)
# - Nginx (installed on system, not Docker)
# - Other web servers
```

## Option 1: Keep Using Port 8080 (Recommended)

✅ **Current setup** - No conflicts, works immediately.

**Access:** `http://your-vm-ip:8080`

## Option 2: Stop the Service Using Port 80

If you want to use port 80, stop the conflicting service:

```bash
# Identify the service
sudo lsof -i :80

# Common commands to stop services:
sudo systemctl stop apache2      # If Apache
sudo systemctl stop nginx        # If system Nginx
sudo systemctl disable apache2   # Prevent auto-start

# Then change docker-compose.yml back to port 80
ports:
  - "80:80"

# Restart Docker
sudo docker compose down
sudo docker compose up -d
```

## Option 3: Use a Different Port

You can use any port above 1024 (doesn't require sudo):

```yaml
# In docker-compose.yml
nginx:
  ports:
    - "7434:80"   # Original port
    - "8000:80"   # Alternative
    - "8080:80"   # Current (standard alternative)
    - "9000:80"   # Another option
```

## Verify No Port Conflicts

Before starting Docker:

```bash
# Check if port is free
sudo lsof -i :8080

# If nothing is returned, port is free ✅
# If output shown, port is in use ❌
```

## Update CORS in .env

Make sure your `.env` file has the correct port in CORS_ORIGINS:

```bash
# Edit .env
nano .env

# Update this line:
CORS_ORIGINS=http://localhost:3000,http://localhost:5000,http://localhost:8080

# Or for production:
CORS_ORIGINS=http://your-vm-ip:8080,http://localhost:8080
```

## Common Port Conflicts

| Port | Common Service |
|------|---------------|
| 80 | Apache2, Nginx, IIS |
| 443 | HTTPS services |
| 5432 | PostgreSQL (system install) |
| 7687 | Neo4j (system install) |
| 8080 | Tomcat, alternative HTTP |

## Network Architecture with Port 8080

```
Internet → Port 8080 (VM)
              ↓
          [Nginx Container: port 80]
              ↓
          [App Container: port 5000]
              ↓               ↓
    [PostgreSQL:5432]  [Neo4j:7687]
```

## Testing

```bash
# Test from VM itself
curl http://localhost:8080

# Test from another machine
curl http://your-vm-ip:8080

# Should return HTML from React app
```

## Firewall Considerations

If you can't access from outside the VM, check firewall:

```bash
# Ubuntu/UFW
sudo ufw allow 8080/tcp
sudo ufw status

# CentOS/Firewalld
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --reload

# Check if port is listening
sudo netstat -tulpn | grep :8080
```

## Production Recommendation

For production, you have two options:

### Option A: Use Nginx on Host (Recommended)
- Install Nginx on the VM (not Docker)
- Configure it to listen on port 80
- Proxy to Docker container on port 8080
- Benefit: Can handle multiple apps, SSL termination

### Option B: Stop System Web Server
- Stop/remove Apache2 or system Nginx
- Let Docker Nginx use port 80
- Change docker-compose back to `"80:80"`

## Summary

**Current Configuration:**
- ✅ External Port: **8080** (no conflicts)
- ✅ Internal Port: 80 (inside Docker)
- ✅ Access: `http://your-vm-ip:8080`

**Changes Made:**
- docker-compose.yml: Changed `"80:80"` to `"8080:80"`
- .env.example: Updated CORS_ORIGINS to include `:8080`

**No more port conflicts!** 🎉
