# 🔍 Memory Monitoring Guide for Embedding Creation

## Quick Start - 3 Steps to Prevent OOM Kills

### **Step 1: Pre-flight Check** ✅

Run this BEFORE starting embedding creation to verify system readiness:

```bash
cd ~/Traceability/nashik-chatbot-pq
./preflight-check.sh
```

**What it checks:**
- ✅ All containers running
- ✅ Available RAM (need >15GB free)
- ✅ CPU load (should be <4.0)
- ✅ Disk space (<85% used)
- ✅ OpenSearch health
- ✅ Neo4j health
- ✅ No recent OOM errors

**Output:**
```
🚀 PRE-FLIGHT CHECK - Embedding Creation
========================================

📦 Container Status:
✅ All containers running

💾 Memory Check:
  Total RAM: 32GB
  Available: 25GB
✅ Sufficient memory available (>20GB)

🔎 Recent OOM Check:
✅ No recent OOM errors

========================================
📋 SUMMARY:
  Passed: 12
  Failed: 0

🎉 All checks passed! System is ready for embedding creation.
```

---

### **Step 2: Start Real-Time Monitoring** 📊

**Open Terminal 1** (for monitoring):

```bash
cd ~/Traceability/nashik-chatbot-pq
./monitoring-during-embeddings.sh
```

This will show:
- 🐳 Live container stats (CPU%, Memory%)
- 💻 VM memory usage
- ⚠️ Alert status (green/yellow/red)
- 🔴 OOM detection
- 📝 Logs to `logs/monitoring/resources_TIMESTAMP.log`

**Example output:**

```
╔══════════════════════════════════════════════════════════════════╗
║           REAL-TIME RESOURCE MONITORING (Embedding)             ║
╚══════════════════════════════════════════════════════════════════╝

⏰ Time: 2026-02-14 12:35:42

🐳 Container Resources:
NAME                      CPU%   MEM USAGE       MEM%
traceability-app          285%   9.8GB / 12GB    81.67%
traceability-opensearch   180%   3.2GB / 5GB     64.00%
traceability-neo4j        8%     6.5GB / 10GB    65.00%
traceability-postgres     3%     450MB / 2GB     22.50%

💻 VM Memory:
Mem:      31Gi       23Gi       5.2Gi
Swap:     4.0Gi      0Gi        4.0Gi

⚠️  Alert Status:
  🟡 App memory elevated: 81.67% (>75%)
  🟢 OpenSearch memory OK: 64%
  🟢 No OOM errors detected

📝 Logging to: logs/monitoring/resources_20260214_123542.log
🔄 Refreshing every 10 seconds... (Ctrl+C to stop)
```

---

### **Step 3: Start Embedding Creation** 🚀

**Open Terminal 2** (for embedding):

```bash
# If containers not running, start them
cd ~/Traceability/nashik-chatbot-pq
docker compose up -d

# Wait 30 seconds for services to be healthy
sleep 30

# Start embedding creation
docker exec -it traceability-app invoke create-embeddings
```

**Watch Terminal 1 for:**
- 🟢 Green = OK (<75% memory)
- 🟡 Yellow = Elevated (75-90% memory)
- 🔴 Red = Critical (>90% memory) → **STOP AND REDUCE BATCH_SIZE**

---

## What to Do When Alerts Appear

### 🟡 Yellow Alert (75-90% memory)

**This is normal during embedding creation.** Keep monitoring.

```
🟡 App memory elevated: 82% (>75%)
```

**Action:** Continue, but watch closely. If it stays >85% for >2 minutes:

```bash
# In Terminal 3, reduce batch size
docker compose down
# Edit .env: BATCH_SIZE=5 (from 10)
docker compose up -d
docker exec -it traceability-app invoke create-embeddings
```

---

### 🔴 Red Alert (>90% memory)

**CRITICAL - Container may get OOM killed!**

```
🔴 App memory HIGH: 94% (>90%)
```

**Immediate actions:**

1. **Stop the embedding process** (Ctrl+C in Terminal 2)
2. **Restart with smaller batch:**

```bash
docker compose down

# Edit .env file
nano .env
# Change:
BATCH_SIZE=5          # Reduce from 10
DOCLING_NUM_THREADS=4 # Reduce from 8

# Restart
docker compose up -d
sleep 30
docker exec -it traceability-app invoke create-embeddings
```

3. **If still getting OOM, increase app memory:**

```bash
# Edit docker-compose.yml
nano docker-compose.yml

# Change app memory limit:
deploy:
  resources:
    limits:
      memory: 16G  # Increase from 12G

# Rebuild
docker compose down
docker compose build app
docker compose up -d
```

---

### 🔴 OOM Kill Detected

```
🔴 OOM DETECTED! Check logs immediately
```

**What happened:** A container ran out of memory and was killed by the OS.

**How to recover:**

```bash
# Check which container was killed
docker ps -a

# View OOM logs
docker logs traceability-app 2>&1 | tail -100 | grep -i "oom\|killed"
docker logs traceability-opensearch 2>&1 | tail -100 | grep -i "oom\|killed"

# Restart the killed container
docker compose restart app
# OR
docker compose restart opensearch

# Then reduce batch size and retry
```

---

## Advanced Monitoring

### Watch Logs in Real-Time (Terminal 3)

```bash
# App logs (embedding progress)
docker logs -f traceability-app

# OpenSearch logs (indexing)
docker logs -f traceability-opensearch

# Filter for errors only
docker logs -f traceability-app 2>&1 | grep -i "error\|oom\|killed"
```

---

### Manual Memory Checks

```bash
# Quick snapshot of all containers
docker stats --no-stream

# Continuous monitoring (like 'top')
docker stats

# Check specific container
docker stats traceability-app --no-stream

# VM memory
free -h

# VM memory + swap
free -h && swapon --show
```

---

### Check Historical Logs

```bash
# View monitoring logs
cat logs/monitoring/resources_*.log | grep "App memory"

# Find peak memory usage
grep "MEM USAGE" logs/monitoring/resources_*.log | sort -k4 -h | tail -5

# Count OOM occurrences
grep -i "oom" logs/monitoring/*.log | wc -l
```

---

## Recommended Settings for 32GB VM

### **Conservative (Safest - Slow)**
```bash
# .env
BATCH_SIZE=5
DOCLING_NUM_THREADS=4
ENABLE_VLM=false
```

**Expected:**
- Memory: ~15GB peak
- Time: ~45-60 min for 229 PDFs
- OOM risk: Very low

---

### **Balanced (Recommended)**
```bash
# .env
BATCH_SIZE=10
DOCLING_NUM_THREADS=8
ENABLE_VLM=false
```

**Expected:**
- Memory: ~20-25GB peak
- Time: ~30-40 min for 229 PDFs
- OOM risk: Low (with monitoring)

---

### **Aggressive (Fastest - Risky)**
```bash
# .env
BATCH_SIZE=15
DOCLING_NUM_THREADS=12
ENABLE_VLM=false

# docker-compose.yml (increase app memory)
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 16G
```

**Expected:**
- Memory: ~25-30GB peak
- Time: ~20-30 min for 229 PDFs
- OOM risk: Moderate (watch closely!)

---

## Troubleshooting

### Swap is Being Used

```bash
# Check swap usage
swapon --show
free -h

# Swap usage means you're running low on RAM
# Reduce BATCH_SIZE or stop other services
```

### Container Keeps Getting Killed

```bash
# Check kernel OOM killer logs
sudo dmesg | grep -i "killed process"

# Increase container memory limits
# OR reduce BATCH_SIZE to 3-5
```

### Monitoring Script Shows Wrong Values

```bash
# Update stats (clear cache)
docker system prune -f

# Restart Docker daemon
sudo systemctl restart docker

# Wait 30 seconds, then re-run monitoring
```

---

## Summary: The Safe Way

```bash
# Terminal 1: Pre-flight check
cd ~/Traceability/nashik-chatbot-pq
./preflight-check.sh

# If passed, start monitoring in Terminal 1
./monitoring-during-embeddings.sh

# Terminal 2: Start embedding
docker exec -it traceability-app invoke create-embeddings

# Terminal 3 (optional): Watch logs
docker logs -f traceability-app

# Keep Terminal 1 visible and watch for 🔴 RED alerts!
```

**Golden Rules:**
1. ✅ Always run preflight check first
2. 📊 Always monitor during embedding creation
3. 🛑 Stop immediately if you see 🔴 RED alerts
4. 📉 Reduce BATCH_SIZE if memory >90%
5. 💾 Keep 2-3GB free RAM at all times
