# Neo4j Memory Configuration Guide

This guide explains how to optimize Neo4j memory settings for different system configurations.

## Understanding Neo4j Memory Components

Neo4j uses three main memory areas:

### 1. Page Cache (`server.memory.pagecache.size`)
- **Purpose**: Caches graph data and native indexes stored on disk
- **Impact**: Primary performance driver - larger cache = fewer disk reads
- **Best Practice**: Allocate the largest portion of available memory here
- **Docker Variable**: `NEO4J_server_memory_pagecache_size`

### 2. JVM Heap (`server.memory.heap.initial_size` and `server.memory.heap.max_size`)
- **Purpose**: Stores transaction state, query execution plans, and intermediate results
- **Impact**: Affects query performance, especially for complex queries
- **Best Practice**: Set initial and max to same value to avoid JVM pauses
- **Docker Variables**:
  - `NEO4J_server_memory_heap_initial__size`
  - `NEO4J_server_memory_heap_max__size`

### 3. Operating System Memory
- **Purpose**: OS processes, file system cache, and other services
- **Best Practice**: Reserve at least 1-2GB, more for systems with lots of RAM

## Memory Allocation Recommendations by System Size

### For 32GB RAM System (Current Configuration)

```yaml
NEO4J_server_memory_pagecache_size: 18G
NEO4J_server_memory_heap_initial__size: 10G
NEO4J_server_memory_heap_max__size: 12G
```

**Breakdown:**
- Page Cache: 18GB (56%)
- Heap: 10-12GB (31-38%)
- OS: 2GB (6%)
- **Total**: 30-32GB

### For 16GB RAM System

```yaml
NEO4J_server_memory_pagecache_size: 8G
NEO4J_server_memory_heap_initial__size: 5G
NEO4J_server_memory_heap_max__size: 6G
```

**Breakdown:**
- Page Cache: 8GB (50%)
- Heap: 5-6GB (31-38%)
- OS: 2GB (12%)
- **Total**: 15-16GB

### For 8GB RAM System

```yaml
NEO4J_server_memory_pagecache_size: 3G
NEO4J_server_memory_heap_initial__size: 2G
NEO4J_server_memory_heap_max__size: 3G
```

**Breakdown:**
- Page Cache: 3GB (38%)
- Heap: 2-3GB (25-38%)
- OS: 2GB (25%)
- **Total**: 7-8GB

### For 64GB RAM System

```yaml
NEO4J_server_memory_pagecache_size: 40G
NEO4J_server_memory_heap_initial__size: 16G
NEO4J_server_memory_heap_max__size: 20G
```

**Breakdown:**
- Page Cache: 40GB (62%)
- Heap: 16-20GB (25-31%)
- OS: 4GB (6%)
- **Total**: 60-64GB

## Using Neo4j's Memory Recommendation Tool

Neo4j provides a built-in tool to calculate optimal memory settings:

```bash
# Inside the Neo4j container
docker-compose exec neo4j neo4j-admin server memory-recommendation --memory=32g

# For different RAM sizes
docker-compose exec neo4j neo4j-admin server memory-recommendation --memory=16g
docker-compose exec neo4j neo4j-admin server memory-recommendation --memory=64g
```

Example output for 32GB:
```
# Memory settings recommendation from neo4j-admin memrec:
#
# Assuming the system is dedicated to running Neo4j and has 32g of memory,
# we recommend a heap size of around 12g, and a page cache of around 18g,
# and that about 2g is left for the operating system, and the native memory
# needed by Lucene and Netty.
```

## How to Apply Memory Configuration

### Option 1: Edit docker-compose.yml (Recommended)

Edit the `docker-compose.yml` file:

```yaml
neo4j:
  image: neo4j:2025.12.1
  environment:
    NEO4J_server_memory_pagecache_size: 18G
    NEO4J_server_memory_heap_initial__size: 10G
    NEO4J_server_memory_heap_max__size: 12G
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

### Option 2: Environment Variables

Create or modify `.env` file:

```env
NEO4J_PAGE_CACHE=18G
NEO4J_HEAP_INITIAL=10G
NEO4J_HEAP_MAX=12G
```

Reference in docker-compose.yml:
```yaml
environment:
  NEO4J_server_memory_pagecache_size: ${NEO4J_PAGE_CACHE}
  NEO4J_server_memory_heap_initial__size: ${NEO4J_HEAP_INITIAL}
  NEO4J_server_memory_heap_max__size: ${NEO4J_HEAP_MAX}
```

## Monitoring Memory Usage

### Check Current Memory Settings

```bash
# View Neo4j logs
docker-compose logs neo4j | grep -i memory

# Connect to Neo4j browser (http://localhost:7474) and run:
CALL dbms.listConfig() YIELD name, value
WHERE name STARTS WITH 'server.memory'
RETURN name, value
```

### Monitor Runtime Memory Usage

```bash
# Check container memory usage
docker stats traceability-neo4j

# Inside container
docker-compose exec neo4j neo4j-admin server memory-recommendation
```

### View Memory Metrics in Browser

1. Open Neo4j Browser: http://localhost:7474
2. Run query:
```cypher
CALL dbms.queryJmx('org.neo4j:*')
YIELD name, attributes
WHERE name CONTAINS 'Memory'
RETURN name, attributes
```

## Performance Tuning Tips

### 1. Page Cache First
- If you have limited memory, prioritize page cache over heap
- Page cache has the most significant impact on read performance
- Rule of thumb: page cache should be at least 2x your heap size

### 2. Match Initial and Max Heap
- Always set `heap_initial__size` = `heap_max__size`
- Prevents JVM garbage collection pauses during heap growth
- Ensures predictable memory allocation

### 3. Monitor and Adjust
- Start with recommendations
- Monitor query performance and memory usage
- Adjust based on your workload patterns:
  - **Read-heavy**: Increase page cache
  - **Write-heavy**: Increase heap
  - **Complex queries**: Increase heap

### 4. Consider Vector Indexes
If using vector indexes (for AI/ML features), add additional memory:
```
Total Memory = Heap + Page Cache + 0.25 × Vector Index Size + OS Memory
```

## Common Issues and Solutions

### Issue: OutOfMemoryError

**Symptom**: Neo4j crashes with heap space errors

**Solutions:**
1. Increase heap max size
2. Optimize queries to use less memory
3. Add pagination to large result sets

### Issue: Slow Query Performance

**Symptom**: Queries take long time, high disk I/O

**Solutions:**
1. Increase page cache size
2. Ensure frequently accessed data fits in cache
3. Monitor `Page Cache Hit Ratio` (should be > 95%)

### Issue: Container Restart Loops

**Symptom**: Neo4j container keeps restarting

**Solutions:**
1. Check if memory allocation exceeds system RAM
2. Reduce page cache and heap sizes
3. Check Docker memory limits: `docker info | grep -i memory`

## Verification Steps

After changing memory configuration:

1. **Restart Neo4j**:
   ```bash
   docker-compose restart neo4j
   ```

2. **Check logs for memory settings**:
   ```bash
   docker-compose logs neo4j | grep -i "heap\|page"
   ```

3. **Verify in Neo4j Browser**:
   ```cypher
   CALL dbms.listConfig() YIELD name, value
   WHERE name CONTAINS 'memory'
   RETURN name, value
   ORDER BY name
   ```

4. **Monitor performance**:
   ```bash
   docker stats traceability-neo4j
   ```

## References

- [Neo4j Memory Configuration Documentation](https://neo4j.com/docs/operations-manual/current/performance/memory-configuration/)
- [Neo4j Docker Image Documentation](https://hub.docker.com/_/neo4j)
- [Neo4j Performance Guide](https://neo4j.com/docs/operations-manual/current/performance/)

## Summary

For a **32GB RAM Ubuntu VM** running Neo4j in Docker:

✅ **Recommended Configuration:**
- Page Cache: **18GB** (primary performance driver)
- Heap Initial: **10GB** (predictable allocation)
- Heap Max: **12GB** (handles query peaks)
- OS Reserve: **2GB** (system stability)

This configuration is already set in your `docker-compose.yml` and provides optimal performance for most graph database workloads.
