# VM Restart & Data Persistence Guide

This guide explains how your Docker setup handles VM restarts and ensures data persistence.

## 🔒 Data Persistence Guarantee

### Your Data is Safe

Your `docker-compose.yml` is configured with **Docker volumes** that persist data on the VM disk:

```yaml
volumes:
  postgres_data:    # PostgreSQL database
  neo4j_data:       # Neo4j graph data
  neo4j_logs:       # Neo4j logs
  neo4j_import:     # Neo4j import files
  neo4j_plugins:    # Neo4j plugins
```

### What Happens During VM Stop/Start

```
8:00 PM - VM Shuts Down
├── Containers stop gracefully
├── Data written to volumes on disk
└── Volumes remain on VM storage ✅

Next Morning - VM Starts
├── Docker service starts
├── Containers auto-start (restart: unless-stopped)
├── Volumes mount to containers
└── All data is restored ✅
```

### Where is Data Stored?

```bash
# Check where Docker volumes are stored
docker volume inspect nashik-chatbot-pq_postgres_data
docker volume inspect nashik-chatbot-pq_neo4j_data

# Typical location on Ubuntu:
/var/lib/docker/volumes/nashik-chatbot-pq_postgres_data/_data
/var/lib/docker/volumes/nashik-chatbot-pq_neo4j_data/_data
```

## 🔄 Auto-Start Configuration

### Already Configured

All services have `restart: unless-stopped` policy:

| Service | Restart Policy | Auto-Start on VM Boot |
|---------|----------------|----------------------|
| PostgreSQL | `unless-stopped` | ✅ Yes |
| Neo4j | `unless-stopped` | ✅ Yes |
| App | `unless-stopped` | ✅ Yes |
| Nginx | `unless-stopped` | ✅ Yes |

### Restart Policies Explained

| Policy | Behavior |
|--------|----------|
| `no` | Never restart ❌ |
| `always` | Always restart (even if manually stopped) |
| `unless-stopped` | **Restart unless manually stopped** ✅ **BEST** |
| `on-failure` | Only restart on error |

**Why `unless-stopped` is best:**
- ✅ Auto-starts when VM boots
- ✅ Auto-restarts if container crashes
- ✅ Respects manual `docker-compose down`
- ✅ Perfect for scheduled VM shutdowns

## ⚙️ One-Time VM Setup

### Step 1: Enable Docker on System Boot

Run this **once** on your Ubuntu VM:

```bash
# Enable Docker service to start on boot
sudo systemctl enable docker

# Verify it's enabled
sudo systemctl is-enabled docker
# Should output: enabled
```

### Step 2: Verify Docker is Running

```bash
# Check Docker service status
sudo systemctl status docker

# Should show: active (running)
```

### Step 3: Test Auto-Start

```bash
# Start your containers
cd /path/to/nashik-chatbot-pq
docker-compose up -d

# Reboot VM to test
sudo reboot

# After VM comes back up (wait 2-3 minutes)
# SSH back in and check:
docker ps

# You should see all 4 containers running:
# - traceability-postgres
# - traceability-neo4j
# - traceability-app
# - traceability-nginx
```

## 🧪 Testing Data Persistence

### Before VM Shutdown

```bash
# 1. Load some data or create a test record
docker-compose exec postgres psql -U postgres -d chatbot -c "CREATE TABLE test_persist (id SERIAL, data TEXT);"
docker-compose exec postgres psql -U postgres -d chatbot -c "INSERT INTO test_persist (data) VALUES ('This should persist!');"

# 2. Verify data exists
docker-compose exec postgres psql -U postgres -d chatbot -c "SELECT * FROM test_persist;"
```

### After VM Restart

```bash
# SSH back into VM after restart

# 1. Check containers are running
docker ps

# 2. Verify data still exists
cd /path/to/nashik-chatbot-pq
docker-compose exec postgres psql -U postgres -d chatbot -c "SELECT * FROM test_persist;"

# Data should still be there! ✅
```

## 📊 Monitoring & Verification

### Check Container Status

```bash
# See all containers and their status
docker-compose ps

# Check how long containers have been running
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Check Volume Usage

```bash
# See all volumes
docker volume ls

# Check volume size
docker system df -v

# Inspect specific volume
docker volume inspect nashik-chatbot-pq_postgres_data
```

### Check Container Logs

```bash
# View startup logs
docker-compose logs --tail=50 postgres
docker-compose logs --tail=50 neo4j
docker-compose logs --tail=50 app

# Follow logs in real-time
docker-compose logs -f
```

## 🚨 Daily VM Shutdown Scenario

### Your Schedule: VM stops at 8 PM, starts next morning

```
┌─────────────────────────────────────────────────────┐
│  8:00 PM - Automated VM Shutdown                    │
├─────────────────────────────────────────────────────┤
│  1. VM shutdown signal received                     │
│  2. Docker containers stop gracefully               │
│  3. Data flushed to volumes                        │
│  4. VM powers off                                   │
│                                                     │
│  ⏸️  VM is OFF overnight - Data safe on disk        │
│                                                     │
│  8:00 AM - VM Powers On (Next Morning)             │
├─────────────────────────────────────────────────────┤
│  1. VM boots up                                     │
│  2. Docker service auto-starts                      │
│  3. Docker reads compose config                     │
│  4. Containers auto-start (restart: unless-stopped) │
│  5. Volumes mount to containers                     │
│  6. App serves traffic with all data intact ✅      │
└─────────────────────────────────────────────────────┘
```

### What You Need to Do

**Nothing!** The system handles everything automatically.

Optional: Set up health monitoring to get notified when VM/containers start.

## 🔧 Advanced: Systemd Service (Optional)

For extra reliability, create a systemd service:

```bash
# Create systemd service file
sudo nano /etc/systemd/system/nashik-chatbot.service
```

Add this content:

```ini
[Unit]
Description=Nashik Chatbot Docker Compose Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/nashik-chatbot-pq
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable nashik-chatbot.service

# Start service
sudo systemctl start nashik-chatbot.service

# Check status
sudo systemctl status nashik-chatbot.service
```

## 📝 Troubleshooting

### Containers Don't Start After Reboot

```bash
# 1. Check Docker service
sudo systemctl status docker

# If not running:
sudo systemctl start docker

# 2. Check container status
docker ps -a

# 3. Manually start if needed
cd /path/to/nashik-chatbot-pq
docker-compose up -d
```

### Data Not Persisting

```bash
# 1. Verify volumes exist
docker volume ls | grep nashik

# 2. Check volume mounts
docker inspect traceability-postgres | grep -A 10 Mounts

# 3. Ensure docker-compose.yml has volume definitions
cat docker-compose.yml | grep -A 5 "volumes:"
```

### Disk Space Issues

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up unused data (CAREFUL!)
docker system prune -a --volumes
# ⚠️  WARNING: This will delete ALL unused volumes!
```

## ✅ Verification Checklist

After setting up, verify everything:

- [ ] Docker service enabled: `sudo systemctl is-enabled docker`
- [ ] Containers running: `docker ps` shows 4 containers
- [ ] Volumes exist: `docker volume ls` shows all volumes
- [ ] Data persists: Test data survives `docker-compose restart`
- [ ] Auto-start works: Reboot VM, containers come back up
- [ ] Logs accessible: `docker-compose logs` works
- [ ] Health checks passing: `docker-compose ps` shows "healthy"

## 🎯 Summary

Your current setup **already guarantees**:

| Concern | Status | Details |
|---------|--------|---------|
| **Data Persistence** | ✅ Configured | Docker volumes store data permanently |
| **Auto-Start** | ✅ Configured | `restart: unless-stopped` on all services |
| **VM Shutdown Safety** | ✅ Safe | Data written to disk before shutdown |
| **Morning Auto-Start** | ✅ Works | Containers start when VM boots |

**What you need to do:**
1. Run `sudo systemctl enable docker` once ✅
2. That's it! Everything else is automatic.

**Daily workflow:**
- 8:00 PM: VM shuts down → Do nothing
- 8:00 AM: VM starts → Do nothing
- Your app is available automatically! 🚀
