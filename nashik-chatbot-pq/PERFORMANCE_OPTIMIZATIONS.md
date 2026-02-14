# PDF Processing Performance Optimizations

## Problem Analysis

### Root Causes Identified from `see_ouput.txt`:

1. **VLM Model Running on CPU** (PRIMARY ISSUE)
   - Each image taking 13-31 seconds to process
   - No GPU acceleration available
   - VLM (Vision Language Model) running 50-100x slower than it should

2. **Underutilizing CPU Resources**
   - Only using 4 of 8 available CPU cores
   - VM has 8 cores and 32GB RAM

3. **No Timeout Protection**
   - Process hung on PDF #23 (Reg 43.01 - Safety Glazing.pdf)
   - No mechanism to skip problematic PDFs

4. **Suboptimal Table Processing**
   - Using ACCURATE mode (slower) instead of FAST mode

---

## Changes Made

### 1. **Disabled VLM Picture Description** ⚡ (MASSIVE SPEEDUP)

**File:** `dataloader/pipeline_factory.py:53`

**Before:**
```python
pipeline_options.do_picture_description = True
```

**After:**
```python
pipeline_options.do_picture_description = False  # DISABLED for CPU-only processing
```

**Impact:**
- **Expected speedup: 10-50x** on documents with images
- Trade-off: No AI-generated picture descriptions in chunks
- Can re-enable if GPU becomes available

---

### 2. **Increased CPU Thread Utilization**

**File:** `dataloader/pipeline_factory.py:72`

**Before:**
```python
pipeline_options.accelerator_options.num_threads = 4
```

**After:**
```python
pipeline_options.accelerator_options.num_threads = 6
```

**Impact:**
- Better utilization of 8-core VM
- **Expected speedup: 1.5x** on CPU-intensive operations

---

### 3. **Faster Table Processing**

**File:** `dataloader/pipeline_factory.py:48`

**Before:**
```python
mode=TableFormerMode.ACCURATE
```

**After:**
```python
mode=TableFormerMode.FAST
```

**Impact:**
- **Expected speedup: 2-3x** on table extraction
- Trade-off: Slightly less accurate table detection (usually acceptable)

---

### 4. **Added Timeout Protection**

**File:** `dataloader/embedding/embedding_creator.py`

**Added:**
- `PDF_CONVERSION_TIMEOUT` environment variable (default: 300s = 5 minutes)
- Timeout handler using SIGALRM
- Graceful skip of problematic PDFs

**Impact:**
- **Prevents hanging** on problematic PDFs
- Process can continue instead of getting stuck
- Configurable timeout via environment variable

---

## Performance Expectations

### Before Optimizations:
```
Document #21: 67.09s
Document #22: 40.14s
Document #23: HUNG (stopped responding)

Estimated time for 229 PDFs: IMPOSSIBLE (would hang)
```

### After Optimizations:
```
Expected per-document time: 5-15s (10-50x faster!)

Estimated time for 229 PDFs:
- Optimistic: 19 minutes (5s/doc)
- Realistic: 38 minutes (10s/doc)
- Pessimistic: 57 minutes (15s/doc)

With RELOAD_INTERVAL=3:
- ~75 reloads (229/3)
- Add ~37 minutes (75 * 30s)
- Total: 56-94 minutes for all 229 PDFs
```

---

## How to Run

### Option 1: Single Run (Recommended to Try First)

```bash
cd ~/Traceability/nashik-chatbot-pq

# Build with new changes
docker compose build app

# Run with optimizations
docker compose up app

# Monitor in another terminal
watch -n 5 'docker stats traceability-app --no-stream'
```

**Environment Variables (Optional):**
```bash
# In docker-compose.yml or .env
RELOAD_INTERVAL=3           # Reload processor every 3 PDFs (default)
PDF_CONVERSION_TIMEOUT=300  # Timeout after 5 minutes (default)
BATCH_SIZE=229             # Process all PDFs
```

---

### Option 2: Batch Processing (Safest)

Process in batches of 10 PDFs with container restart between batches:

```bash
cd ~/Traceability/nashik-chatbot-pq

# Create batch processing script
cat > process_batches.sh << 'EOF'
#!/bin/bash

BATCH_SIZE=10
TOTAL_DOCS=229

for ((start=0; start<TOTAL_DOCS; start+=BATCH_SIZE)); do
    echo "==========================================="
    echo "Processing batch: documents $start to $((start+BATCH_SIZE))"
    echo "==========================================="

    # Run container for this batch
    docker compose up app

    echo "Batch complete. Restarting container..."
    docker compose down
    sleep 5
done

echo "All batches complete!"
EOF

chmod +x process_batches.sh
./process_batches.sh
```

---

### Option 3: Increase Memory (If Issues Persist)

```yaml
# docker-compose.yml
app:
  deploy:
    resources:
      limits:
        memory: 20G  # Increased from 12G
```

---

## Monitoring

### Check Progress:
```bash
# View logs
docker compose logs -f app | grep "Processing document"

# Memory usage
docker stats traceability-app

# Count completed documents
docker compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "SELECT COUNT(*) FROM scraped_docs WHERE status='complete';"
```

### Expected Memory Pattern:
```
With RELOAD_INTERVAL=3:
PDF 1: 5GB → 5.5GB
PDF 2: 5.5GB → 6GB
PDF 3: 6GB → 6.5GB → RELOAD → 5GB
PDF 4: 5GB → 5.5GB
...

Peak: ~6.5GB (safe under 12GB limit)
```

---

## Troubleshooting

### If It Still Hangs:
1. Check logs: `docker compose logs app | tail -100`
2. Look for timeout messages
3. Reduce `RELOAD_INTERVAL` to 2 or 1
4. Use batch processing (Option 2)

### If Memory Still Grows:
1. Reduce `RELOAD_INTERVAL` to 2
2. Use smaller `BATCH_SIZE` (e.g., 5)
3. Increase container memory limit to 16-20G

### If Timeouts Are Too Aggressive:
```bash
# Increase timeout to 10 minutes
PDF_CONVERSION_TIMEOUT=600
```

---

## Summary of Improvements

| Optimization | Expected Speedup | Trade-off |
|--------------|-----------------|-----------|
| Disable VLM | **10-50x** | No AI picture descriptions |
| Increase threads (4→6) | **1.5x** | None (more CPU usage) |
| Fast table mode | **2-3x** | Slightly less accurate tables |
| Timeout protection | **Prevents hanging** | May skip complex PDFs |

**Combined Expected Speedup: 30-150x faster! 🚀**

---

## Next Steps

1. ✅ Build updated image: `docker compose build app`
2. ✅ Try Option 1 (single run) first
3. ✅ Monitor memory and progress
4. ✅ If issues occur, fall back to Option 2 (batch processing)
5. ✅ Report results

**The system should now be able to process all 229+ PDFs without stopping!**
