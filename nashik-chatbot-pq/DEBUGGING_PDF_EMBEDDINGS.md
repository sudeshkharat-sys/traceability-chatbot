# Debugging PDF Embedding Pipeline

This guide helps you diagnose and fix issues with PDF embedding processing.

## Quick Diagnostic

Run the diagnostic script to check system status:

```bash
# Inside the app container
python diagnostic_check.py
```

This will show:
- Postgres database status (document counts, incomplete documents)
- OpenSearch connection and index status
- Memory usage
- Data mismatches between Postgres and OpenSearch

## Common Issues and Solutions

### 1. Processing Stops After N Documents

**Symptoms:**
- Data loading stops after processing 4-10 PDFs
- No error messages in logs
- Process appears to hang

**Root Causes:**
- **OpenSearch Out of Memory** (MOST COMMON)
- Application container out of memory
- Network timeout to OpenSearch

**Solutions:**

#### A. Increase OpenSearch Memory (CRITICAL)

The recent fix increased OpenSearch memory from 512MB to 4GB. If you still have issues:

1. Edit `docker-compose.yml`:
   ```yaml
   opensearch:
     environment:
       - "OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx4g"  # Adjust as needed
     deploy:
       resources:
         limits:
           memory: 6G  # Should be heap + ~2GB overhead
   ```

2. Restart services:
   ```bash
   docker-compose down
   docker-compose up -d opensearch
   ```

3. Monitor OpenSearch logs:
   ```bash
   docker logs -f traceability-opensearch
   ```

   Look for:
   - `OutOfMemoryError`
   - `circuit_breaking_exception`
   - `rejected execution`

#### B. Monitor Memory Usage

Watch container memory in real-time:
```bash
docker stats traceability-app traceability-opensearch traceability-postgres traceability-neo4j
```

If app container reaches memory limit, increase in `docker-compose.yml`:
```yaml
app:
  deploy:
    resources:
      limits:
        memory: 14G  # Increase if needed
```

### 2. Documents in Postgres but Not in OpenSearch

**Symptoms:**
- `diagnostic_check.py` shows chunk count mismatch
- Postgres has more chunks than OpenSearch has documents

**Root Cause:**
- OpenSearch failed during upsertion (likely memory)
- Documents were partially processed

**Solution:**

1. Check OpenSearch logs for errors:
   ```bash
   docker logs traceability-opensearch | grep -i error
   ```

2. Reset incomplete documents:
   ```python
   # In Python shell or script
   from app.connectors.state_db_connector import StateDBConnector
   from datetime import datetime

   db = StateDBConnector()
   db.execute_update(
       "UPDATE scraped_docs SET status = 'incomplete' WHERE status = 'complete'",
       {"updated_at": datetime.utcnow()}
   )
   db.close()
   ```

3. Reprocess with increased memory

### 3. Docling Conversion Slow or Failing

**Symptoms:**
- Long processing time per document
- Conversion phase taking >30s per PDF

**Solutions:**

#### A. Increase CPU Threads

Edit `dataloader/pipeline_factory.py`:
```python
pipeline_options.accelerator_options.num_threads = 4  # Adjust based on CPU cores
```

Recommended settings:
- 4 cores: `num_threads = 2`
- 8 cores: `num_threads = 4`
- 16+ cores: `num_threads = 6-8`

#### B. Disable Resource-Intensive Features

If you don't need picture descriptions:
```python
pipeline_options.do_picture_description = False
```

If you don't need table images:
```python
pipeline_options.generate_table_images = False
```

### 4. Configuration Errors

**Symptoms:**
- `AttributeError: 'Settings' object has no attribute 'DOCLING_VLM_MODEL'`

**Solution:**

Ensure `.env` file has:
```bash
DOCLING_VLM_MODEL=SmolDocling-256M-preview
```

And `app/config/config.py` includes:
```python
DOCLING_VLM_MODEL: str = "SmolDocling-256M-preview"
```

## Monitoring During Processing

### View Processing Logs

```bash
# Follow app logs
docker logs -f traceability-app

# Filter for embedding processor
docker logs -f traceability-app | grep -i "embedding\|document"

# See errors only
docker logs -f traceability-app | grep -i "error\|exception"
```

### Understanding Log Output

New logging format shows processing phases:

```
[1/3] Converting PDF with Docling...
✓ Conversion completed in 8.5s

[2/3] Chunking document...
✓ Chunking completed in 1.2s - 45 chunks created

[3/3] Embedding and upserting 45 chunks to OpenSearch & Postgres...
Flushing batch of 45 chunks to OpenSearch...
✓ OpenSearch batch upsert completed in 12.3s
✓ Postgres batch upsert completed in 0.8s
✓ Embedding phase completed in 13.1s

✓ Document processed in 22.8s: 45 processed, 45 created, 0 updated, 0 skipped, 0 errors
```

If processing hangs, note which phase it's stuck on:
- **Phase 1 (Conversion):** Docling issue - check CPU/memory
- **Phase 2 (Chunking):** Usually fast - check for exceptions
- **Phase 3 (Embedding):** Most common - OpenSearch memory issue

### Check OpenSearch Health

```bash
# Cluster health
curl http://localhost:9200/_cluster/health?pretty

# Index stats
curl http://localhost:9200/standard_guidelines_index/_stats?pretty

# Check for circuit breakers (memory protection)
curl http://localhost:9200/_nodes/stats/breaker?pretty
```

## Performance Optimization

### Current Memory Allocation (32GB VM)

| Service | Memory | Purpose |
|---------|--------|---------|
| App | 12GB | PDF processing, embeddings |
| Neo4j | 10GB | Graph database |
| OpenSearch | 6GB | Vector embeddings |
| Postgres | 2GB | Metadata storage |
| System | 2GB | OS and overhead |

### Tuning for Large Batches

If processing 234+ PDFs:

1. **Batch Processing:** Process in smaller batches
   ```bash
   # Process first 50 documents
   # Then monitor and continue
   ```

2. **Reduce Chunk Batch Size:** Edit `embedding_creator.py`
   ```python
   CHUNK_BATCH_SIZE = 25  # Reduce from 50 if memory constrained
   ```

3. **More Aggressive GC:** Force garbage collection more often
   ```python
   # In process_document loop
   if idx % 5 == 0:  # Every 5 documents
       gc.collect()
   ```

## Getting Help

When reporting issues, include:

1. **Diagnostic output:**
   ```bash
   python diagnostic_check.py > diagnostic.txt 2>&1
   ```

2. **Container stats during processing:**
   ```bash
   docker stats --no-stream > stats.txt
   ```

3. **Recent logs:**
   ```bash
   docker logs --tail 200 traceability-app > app.log 2>&1
   docker logs --tail 200 traceability-opensearch > opensearch.log 2>&1
   ```

4. **Number and size of PDFs:**
   - Total count
   - Average pages per PDF
   - Largest PDF size

## Rollback

If new changes cause issues:

```bash
# Restore original docker-compose.yml
git checkout HEAD~1 docker-compose.yml

# Restart services
docker-compose down
docker-compose up -d
```
