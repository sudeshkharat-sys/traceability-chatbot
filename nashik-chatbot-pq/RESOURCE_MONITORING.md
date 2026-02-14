# Resource Monitoring Guide

## Quick Resource Check

### Monitor All Containers
```bash
# Real-time resource usage (CPU, RAM, Network, Disk I/O)
docker stats

# Detailed view with container names
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"
```

### Check Individual Container
```bash
# App container
docker stats traceability-app --no-stream

# OpenSearch (during embedding creation)
docker stats traceability-opensearch --no-stream

# Neo4j
docker stats traceability-neo4j --no-stream

# Postgres
docker stats traceability-postgres --no-stream
```

---

## Expected Resource Usage

### During Embedding Creation (Heavy Load)
```
Container                CPU%    Memory          Network
-------------------------------------------------------------
traceability-app        250-300%  8-12GB (of 12GB)  Moderate
traceability-opensearch 150-200%  3-5GB  (of 5GB)   High
traceability-neo4j      5-10%     6-8GB  (of 10GB)  Low
traceability-postgres   2-5%      500MB  (of 2GB)   Low
traceability-nginx      <1%       50MB   (of 256MB) Low
```

**Total Peak Usage:** ~18-25GB RAM, 4-6 CPU cores

### During Normal Chat Operations (Light Load)
```
Container                CPU%    Memory          Network
-------------------------------------------------------------
traceability-app        5-15%     2-4GB  (of 12GB)  Low
traceability-opensearch 10-30%    2-3GB  (of 5GB)   Moderate
traceability-neo4j      20-50%    6-8GB  (of 10GB)  Moderate
traceability-postgres   2-5%      300MB  (of 2GB)   Low
traceability-nginx      1-2%      40MB   (of 256MB) Low
```

**Total Normal Usage:** ~11-16GB RAM, 0.5-1.5 CPU cores

---

## Warning Signs

### Memory Issues
```bash
# Check if containers are hitting memory limits
docker inspect traceability-app | grep -A5 "Memory"

# Watch for OOM kills in logs
docker logs traceability-app 2>&1 | grep -i "killed\|oom\|out of memory"
docker logs traceability-opensearch 2>&1 | grep -i "killed\|oom"
```

**Symptoms:**
- App crashes during PDF processing → Increase app memory or reduce `BATCH_SIZE`
- OpenSearch crashes during indexing → Increase OpenSearch heap (`OPENSEARCH_JAVA_OPTS`)
- Neo4j slow queries → Check pagecache usage, might need more memory

### CPU Bottlenecks
```bash
# Check if containers are CPU-throttled
docker stats --no-stream | grep -E "traceability-(app|opensearch)"
```

**Symptoms:**
- App CPU at 300% (3 cores max) → PDF processing is maxed out (expected during embeddings)
- OpenSearch CPU high → Indexing or search queries are intensive
- Neo4j CPU high → Complex graph queries running

### Disk I/O Issues
```bash
# Check disk usage
docker system df -v

# Volume sizes
docker volume ls
docker volume inspect postgres_data neo4j_data opensearch_data
```

---

## Optimization Tips

### 1. **If App Runs Out of Memory During Embedding:**
```yaml
# In docker-compose.yml, increase app memory
deploy:
  resources:
    limits:
      memory: 16G  # Increase from 12G
```

### 2. **If OpenSearch Runs Out of Memory:**
```yaml
# Increase heap size (but keep it < 50% of container limit)
environment:
  - "OPENSEARCH_JAVA_OPTS=-Xms3g -Xmx5g"  # Increase from -Xmx4g
deploy:
  resources:
    limits:
      memory: 7G  # Increase container limit too
```

### 3. **If PDF Processing is Too Slow:**
```bash
# Increase app CPU cores
deploy:
  resources:
    limits:
      cpus: '4.0'  # Increase from 3.0
```

### 4. **If System Runs Out of RAM:**
```bash
# Reduce batch size in .env
BATCH_SIZE=5  # Reduce from 10

# Process fewer documents at once
DOCLING_NUM_THREADS=4  # Reduce from 8
```

---

## VM-Level Monitoring

### Check VM Resources
```bash
# Overall memory usage
free -h

# CPU usage by process
top -o %CPU

# Top memory consumers
ps aux --sort=-%mem | head -n 10

# Disk usage
df -h

# I/O wait time
iostat -x 1 5
```

### Check Docker Daemon
```bash
# Docker daemon resource usage
systemctl status docker

# Docker daemon logs
journalctl -u docker -f
```

---

## Troubleshooting Commands

### Restart Specific Container
```bash
# If a container is misbehaving
docker compose restart app
docker compose restart opensearch
docker compose restart neo4j
```

### Force Resource Cleanup
```bash
# Clean up dangling images/containers
docker system prune -a

# Remove unused volumes (CAREFUL!)
docker volume prune
```

### Emergency Stop
```bash
# Stop all containers gracefully
docker compose down

# Force kill all containers
docker compose kill
```

---

## Recommended Alerts

Set up monitoring with these thresholds:

| Metric | Warning | Critical |
|--------|---------|----------|
| Total RAM usage | > 28GB (87%) | > 30GB (94%) |
| App memory | > 10GB | > 11.5GB |
| OpenSearch memory | > 4GB | > 4.8GB |
| CPU load average | > 6.0 | > 7.5 |
| Disk usage (/) | > 80% | > 90% |
| Docker volume size | > 50GB | > 75GB |

---

## Production Recommendations

1. **Enable Docker metrics endpoint** for Prometheus/Grafana monitoring
2. **Set up log rotation** to prevent disk fills
3. **Configure swap** (4-8GB) as emergency buffer
4. **Monitor with external tools** (Datadog, New Relic, etc.)
5. **Set up alerts** for memory/CPU thresholds
