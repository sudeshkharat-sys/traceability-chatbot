# Docker Container Health Check Guide

This guide explains how to verify that all Docker containers are running correctly and the application is working.

## Quick Health Check Commands

### 1. Check Container Status

```bash
cd ~/Traceability/nashik-chatbot-pq
sudo docker compose ps
```

**Expected Output:**
```
NAME                          STATUS              PORTS
nashik-chatbot-pq-app-1      Up (healthy)        0.0.0.0:5000->5000/tcp
nashik-chatbot-pq-nginx-1    Up                  0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
nashik-chatbot-pq-postgres-1 Up (healthy)        5432/tcp
nashik-chatbot-pq-neo4j-1    Up                  7474/tcp, 7687/tcp
```

✅ All containers should show **"Up"** status

---

## 2. Application Health Endpoints

Your FastAPI application has built-in health check endpoints:

### Basic Health Check

```bash
curl http://localhost/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "Thar Roxx Quality Intelligence API"
}
```

### Detailed Health Check (with Database Connectivity)

```bash
curl http://localhost/health/detailed
```

**Expected Response (All Healthy):**
```json
{
  "status": "healthy",
  "service": "Thar Roxx Quality Intelligence API",
  "components": {
    "neo4j": {
      "status": "connected",
      "error": null
    },
    "postgresql": {
      "status": "connected",
      "error": null
    }
  }
}
```

**If Degraded:**
```json
{
  "status": "degraded",
  "service": "Thar Roxx Quality Intelligence API",
  "components": {
    "neo4j": {
      "status": "error",
      "error": "Connection refused"
    },
    "postgresql": {
      "status": "connected",
      "error": null
    }
  }
}
```

### System Statistics

```bash
curl http://localhost/stats
```

**Expected Response:**
```json
{
  "stats": {
    "neo4j": {
      "parts": 0,
      "vehicles": 0,
      "warranty_claims": 0,
      "batches": 0,
      "vendors": 0
    }
  }
}
```

### Initialization Status

```bash
curl http://localhost/initialization
```

**Expected Response:**
```json
{
  "initialized": true,
  "results": {
    "database": {
      "success": true,
      "message": "Database initialized successfully"
    },
    "neo4j": {
      "success": true,
      "message": "Neo4j connection established"
    }
  }
}
```

### List Prompts

```bash
curl http://localhost/prompts
```

**Expected Response:**
```json
{
  "prompts": [
    {
      "key": "system",
      "name": "System Prompt",
      "updated_at": "2024-01-20T10:30:00",
      "content_length": 1234
    }
  ],
  "count": 1
}
```

---

## 3. Check Container Logs

### View All Logs

```bash
sudo docker compose logs --tail=50
```

### View Specific Service Logs

**Application Logs:**
```bash
sudo docker compose logs app --tail=50 -f
```

Look for:
- ✅ "Application startup complete"
- ✅ "Uvicorn running on http://0.0.0.0:5000"
- ❌ Any error messages or tracebacks

**Nginx Logs:**
```bash
sudo docker compose logs nginx --tail=50
```

Look for:
- ✅ "start worker processes"
- ❌ "cannot load certificate" (SSL issue)
- ❌ "502 Bad Gateway" (app not reachable)

**PostgreSQL Logs:**
```bash
sudo docker compose logs postgres --tail=50
```

Look for:
- ✅ "database system is ready to accept connections"
- ❌ "FATAL: password authentication failed"

**Neo4j Logs:**
```bash
sudo docker compose logs neo4j --tail=50
```

Look for:
- ✅ "Started."
- ✅ "Remote interface available at http://localhost:7474/"
- ❌ "Unable to start" (memory/config issue)

---

## 4. Test Database Connections

### PostgreSQL Connection Test

```bash
sudo docker compose exec postgres pg_isready -U postgres
```

**Expected:**
```
postgres:5432 - accepting connections
```

### Connect to PostgreSQL

```bash
sudo docker compose exec postgres psql -U postgres -d chatbot
```

**Run a test query:**
```sql
\dt  -- List all tables
SELECT COUNT(*) FROM checkpoints;  -- Count checkpoints
\q   -- Quit
```

### Neo4j Connection Test

```bash
sudo docker compose exec neo4j cypher-shell -u neo4j -p password "RETURN 1 as test;"
```

**Expected:**
```
test
1
```

### Access Neo4j Browser

Open in browser: `http://YOUR_VM_IP:7474`

- Username: `neo4j`
- Password: Check your `.env` file for `NEO4J_PASSWORD`

Run a test query:
```cypher
MATCH (n) RETURN count(n) as node_count;
```

---

## 5. Test Network Connectivity

### Check Ports Listening

```bash
sudo netstat -tulpn | grep -E ':80|:443|:5000|:5432|:7474|:7687'
```

**Expected:**
```
tcp  0.0.0.0:80     LISTEN  docker-proxy
tcp  0.0.0.0:443    LISTEN  docker-proxy
tcp  0.0.0.0:5000   LISTEN  docker-proxy
tcp  0.0.0.0:7474   LISTEN  docker-proxy
tcp  0.0.0.0:7687   LISTEN  docker-proxy
```

### Test HTTP Access

```bash
# From VM
curl -I http://localhost
curl -I http://localhost:5000

# From outside (replace with your VM IP)
curl -I http://YOUR_VM_IP
```

**Expected HTTP Status: 200 OK**

### Test HTTPS Access (if SSL configured)

```bash
curl -I https://localhost --insecure
```

---

## 6. Browser Tests

### Main Application

Open: `http://YOUR_VM_IP`

✅ Should load React frontend
✅ No console errors (F12 → Console tab)
✅ Network requests successful (F12 → Network tab)

### Neo4j Browser

Open: `http://YOUR_VM_IP:7474`

✅ Login page should appear
✅ Can login with credentials
✅ Can run queries

---

## 7. Check Resource Usage

### Container Resource Usage

```bash
sudo docker stats --no-stream
```

**Example Output:**
```
CONTAINER           CPU %     MEM USAGE / LIMIT     MEM %
neo4j              2.5%      20GiB / 32GiB        62.5%
app                1.2%      500MiB / 32GiB       1.5%
postgres           0.5%      200MiB / 32GiB       0.6%
nginx              0.1%      10MiB / 32GiB        0.03%
```

**Neo4j Memory:** Should use 18-20GB (Page Cache + Heap)
**App Memory:** Typically 200-500MB
**PostgreSQL:** Typically 100-300MB

### Disk Usage

```bash
sudo docker system df
```

**Check volumes:**
```bash
sudo docker volume ls
sudo docker volume inspect nashik-chatbot-pq_postgres_data
sudo docker volume inspect nashik-chatbot-pq_neo4j_data
```

---

## 8. Automated Health Check Script

Save as `health-check.sh`:

```bash
#!/bin/bash

echo "========================================"
echo "  Docker Container Health Check"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to project directory
cd ~/Traceability/nashik-chatbot-pq || exit 1

echo "1. Container Status"
echo "-------------------"
sudo docker compose ps
echo ""

echo "2. Basic Health Endpoint"
echo "------------------------"
BASIC_HEALTH=$(curl -s http://localhost/health)
echo "$BASIC_HEALTH" | jq '.' 2>/dev/null || echo "$BASIC_HEALTH"
echo ""

echo "3. Detailed Health Endpoint"
echo "---------------------------"
DETAILED_HEALTH=$(curl -s http://localhost/health/detailed)
echo "$DETAILED_HEALTH" | jq '.' 2>/dev/null || echo "$DETAILED_HEALTH"

# Check if healthy
if echo "$DETAILED_HEALTH" | grep -q '"status": "healthy"'; then
    echo -e "${GREEN}✓ Application is healthy${NC}"
else
    echo -e "${RED}✗ Application is degraded or unhealthy${NC}"
fi
echo ""

echo "4. PostgreSQL Connection"
echo "------------------------"
PG_STATUS=$(sudo docker compose exec -T postgres pg_isready -U postgres 2>&1)
echo "$PG_STATUS"
if echo "$PG_STATUS" | grep -q "accepting connections"; then
    echo -e "${GREEN}✓ PostgreSQL is healthy${NC}"
else
    echo -e "${RED}✗ PostgreSQL has issues${NC}"
fi
echo ""

echo "5. Neo4j Connection"
echo "-------------------"
NEO4J_STATUS=$(sudo docker compose exec -T neo4j cypher-shell -u neo4j -p password "RETURN 1;" 2>&1)
if echo "$NEO4J_STATUS" | grep -q "1"; then
    echo -e "${GREEN}✓ Neo4j is healthy${NC}"
else
    echo -e "${RED}✗ Neo4j has issues${NC}"
    echo "$NEO4J_STATUS"
fi
echo ""

echo "6. Listening Ports"
echo "------------------"
sudo netstat -tulpn | grep -E ':80|:443|:5000|:7474|:7687' || echo "No ports listening"
echo ""

echo "7. Recent Application Logs (Last 10 lines)"
echo "-------------------------------------------"
sudo docker compose logs app --tail=10
echo ""

echo "8. Resource Usage"
echo "-----------------"
sudo docker stats --no-stream
echo ""

echo "========================================"
echo "  Health Check Complete"
echo "========================================"
```

**Run it:**
```bash
chmod +x health-check.sh
./health-check.sh
```

**Save output to file:**
```bash
./health-check.sh > health-report.txt 2>&1
cat health-report.txt
```

---

## 9. Common Issues & Solutions

### Issue: Container Exited or Restarting

**Diagnose:**
```bash
sudo docker compose ps
sudo docker compose logs <service-name> --tail=100
```

**Common Causes:**
- ❌ Missing environment variables in `.env`
- ❌ Database connection failed
- ❌ Port already in use
- ❌ Out of memory

**Fix:**
```bash
# Check environment variables
cat .env

# Restart specific container
sudo docker compose restart <service-name>

# Or restart all
sudo docker compose down && sudo docker compose up -d
```

### Issue: 502 Bad Gateway

**Means:** Nginx can't reach the app container

**Fix:**
```bash
# Check if app is running
sudo docker compose ps app

# Check app logs
sudo docker compose logs app --tail=50

# Restart app
sudo docker compose restart app
```

### Issue: Health Endpoint Returns 503 or Error

**Means:** Database connection issues

**Fix:**
```bash
# Check database containers
sudo docker compose ps postgres neo4j

# Check database logs
sudo docker compose logs postgres --tail=50
sudo docker compose logs neo4j --tail=50

# Test database connections manually
sudo docker compose exec postgres pg_isready -U postgres
sudo docker compose exec neo4j cypher-shell -u neo4j -p password "RETURN 1;"

# Restart databases
sudo docker compose restart postgres neo4j
```

### Issue: Can't Access from Browser

**Check Firewall:**
```bash
# Ubuntu/Debian
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 7474/tcp

# Reload firewall
sudo ufw reload
```

### Issue: Neo4j Out of Memory

**Symptoms:**
- Neo4j container keeps restarting
- Logs show "OutOfMemoryError"

**Fix:**
```bash
# Reduce memory in docker-compose.yml
# For 16GB RAM system:
NEO4J_server_memory_pagecache_size: 8G
NEO4J_server_memory_heap_initial__size: 4G
NEO4J_server_memory_heap_max__size: 6G

# Restart
sudo docker compose down
sudo docker compose up -d
```

---

## 10. Production Health Monitoring

### Set Up Automated Health Checks

**Option 1: Cron Job (Simple)**

```bash
# Edit crontab
crontab -e

# Add health check every 5 minutes
*/5 * * * * /home/user/Traceability/nashik-chatbot-pq/health-check.sh >> /var/log/docker-health.log 2>&1
```

**Option 2: Systemd Timer**

Create `/etc/systemd/system/docker-health.service`:
```ini
[Unit]
Description=Docker Health Check

[Service]
Type=oneshot
ExecStart=/home/user/Traceability/nashik-chatbot-pq/health-check.sh
```

Create `/etc/systemd/system/docker-health.timer`:
```ini
[Unit]
Description=Run Docker Health Check Every 5 Minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

**Enable:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable docker-health.timer
sudo systemctl start docker-health.timer
```

---

## 11. Complete Verification Checklist

Use this checklist to verify everything is working:

- [ ] All 4 containers show "Up" status: `sudo docker compose ps`
- [ ] `/health` endpoint returns "healthy": `curl http://localhost/health`
- [ ] `/health/detailed` shows all components "connected": `curl http://localhost/health/detailed`
- [ ] PostgreSQL accepting connections: `sudo docker compose exec postgres pg_isready`
- [ ] Neo4j responding to queries: `sudo docker compose exec neo4j cypher-shell -u neo4j -p password "RETURN 1;"`
- [ ] Ports 80 and 443 listening: `sudo netstat -tulpn | grep -E ':80|:443'`
- [ ] HTTP access works: `curl http://localhost`
- [ ] No error messages in logs: `sudo docker compose logs --tail=50`
- [ ] Application loads in browser: `http://YOUR_VM_IP`
- [ ] Neo4j browser accessible: `http://YOUR_VM_IP:7474`

---

## 12. Getting Help

If you encounter issues:

1. **Capture logs:**
   ```bash
   sudo docker compose logs > docker-logs.txt
   ./health-check.sh > health-status.txt
   ```

2. **Check container status:**
   ```bash
   sudo docker compose ps -a
   sudo docker stats --no-stream
   ```

3. **Review configuration:**
   ```bash
   cat .env
   sudo docker compose config
   ```

4. **Share the output with your team or support**

---

## Quick Reference Commands

```bash
# Check status
sudo docker compose ps

# Basic health check
curl http://localhost/health | jq '.'

# Detailed health check
curl http://localhost/health/detailed | jq '.'

# View logs
sudo docker compose logs -f

# Restart all
sudo docker compose restart

# Full restart
sudo docker compose down && sudo docker compose up -d

# Run health script
./health-check.sh
```
