#!/bin/bash
# ============================================================================
# Safe Batch Processing for Embeddings
# Processes PDFs in small batches with container restarts to prevent OOM
# ============================================================================

set -e  # Exit on error

# Configuration
BATCH_SIZE=${BATCH_SIZE:-10}          # Process 10 PDFs per batch
RESTART_DELAY=${RESTART_DELAY:-10}    # Wait 10s between batches
MAX_RETRIES=${MAX_RETRIES:-3}         # Retry failed batches up to 3 times

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Safe Batch Embedding Processing Script             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Configuration:"
echo "  Batch size: $BATCH_SIZE PDFs per batch"
echo "  Restart delay: ${RESTART_DELAY}s between batches"
echo "  Max retries: $MAX_RETRIES attempts per batch"
echo ""

# Get total document count
echo -e "${BLUE}📊 Checking pending documents...${NC}"
TOTAL_DOCS=$(docker exec -it traceability-app python3 -c "
import sys
sys.path.append('/app')
from app.connectors.state_db_connector import StateDBConnector
from app.queries import DataloaderQueries

db = StateDBConnector()
rows = db.execute_query(DataloaderQueries.GET_INCOMPLETE_DOCUMENTS)
print(len(rows))
db.close()
" 2>/dev/null | tr -d '\r')

if [ -z "$TOTAL_DOCS" ] || [ "$TOTAL_DOCS" -eq 0 ]; then
    echo -e "${GREEN}✅ No incomplete documents found. All done!${NC}"
    exit 0
fi

echo -e "${GREEN}Found $TOTAL_DOCS incomplete documents${NC}"
echo ""

# Calculate number of batches
TOTAL_BATCHES=$(( (TOTAL_DOCS + BATCH_SIZE - 1) / BATCH_SIZE ))
echo -e "${BLUE}📦 Will process in $TOTAL_BATCHES batch(es)${NC}"
echo ""

# Create log directory
mkdir -p logs/batch_processing
LOG_FILE="logs/batch_processing/batch_run_$(date +%Y%m%d_%H%M%S).log"
echo "📝 Logging to: $LOG_FILE"
echo ""

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to process a batch
process_batch() {
    local batch_num=$1
    local attempt=$2

    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "BATCH $batch_num/$TOTAL_BATCHES (Attempt $attempt/$MAX_RETRIES)"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Start containers if not running
    log "Starting containers..."
    docker compose up -d >> "$LOG_FILE" 2>&1

    # Wait for services to be healthy
    log "Waiting for services to be ready..."
    sleep 30

    # Check health
    if ! docker exec traceability-app python3 -c "import requests; requests.get('http://localhost:5000/health')" 2>/dev/null; then
        log "ERROR: App is not healthy!"
        return 1
    fi

    # Process batch
    log "Processing batch of $BATCH_SIZE documents..."
    echo -e "${YELLOW}⚙️  Processing batch $batch_num/$TOTAL_BATCHES...${NC}"

    # Run with batch size limit and strict memory cleanup
    if docker exec traceability-app bash -c "
        export BATCH_SIZE=$BATCH_SIZE
        export RELOAD_INTERVAL=1
        export PYTHONMALLOC=malloc
        python3 -c '
from dataloader.document_embedding_processor import DocumentEmbeddingProcessor
import gc

processor = DocumentEmbeddingProcessor()
try:
    stats = processor.run(batch_size=$BATCH_SIZE)
    print(f\"Batch completed: {stats}\")
finally:
    processor.close()
    gc.collect()
    gc.collect()
    gc.collect()
'
    " >> "$LOG_FILE" 2>&1; then
        log "✅ Batch $batch_num completed successfully"
        echo -e "${GREEN}✅ Batch $batch_num/$TOTAL_BATCHES completed${NC}"
        return 0
    else
        log "❌ Batch $batch_num failed"
        echo -e "${RED}❌ Batch $batch_num/$TOTAL_BATCHES failed${NC}"
        return 1
    fi
}

# Function to restart containers
restart_containers() {
    log "Restarting containers to clear memory..."
    echo -e "${BLUE}🔄 Restarting containers...${NC}"

    docker compose down >> "$LOG_FILE" 2>&1
    sleep 5

    # Clear any orphaned processes
    docker system prune -f >> "$LOG_FILE" 2>&1

    log "Containers stopped, waiting ${RESTART_DELAY}s before next batch..."
    sleep "$RESTART_DELAY"
}

# Main processing loop
batch_num=1
successful_batches=0
failed_batches=0

while [ "$batch_num" -le "$TOTAL_BATCHES" ]; do
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  Batch $batch_num of $TOTAL_BATCHES${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

    # Try processing the batch with retries
    success=false
    for attempt in $(seq 1 $MAX_RETRIES); do
        if process_batch "$batch_num" "$attempt"; then
            success=true
            ((successful_batches++))
            break
        else
            log "⚠️  Batch $batch_num attempt $attempt failed"

            if [ "$attempt" -lt "$MAX_RETRIES" ]; then
                log "Retrying after container restart..."
                restart_containers
            fi
        fi
    done

    if [ "$success" = false ]; then
        log "❌ Batch $batch_num failed after $MAX_RETRIES attempts"
        ((failed_batches++))

        # Ask user if they want to continue
        echo -e "${RED}Batch $batch_num failed after $MAX_RETRIES attempts${NC}"
        read -p "Continue with next batch? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "User aborted processing"
            break
        fi
    fi

    # Restart containers between batches (except for the last one)
    if [ "$batch_num" -lt "$TOTAL_BATCHES" ]; then
        restart_containers
    fi

    ((batch_num++))
done

# Final summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    FINAL SUMMARY                           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "FINAL SUMMARY"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Total batches: $TOTAL_BATCHES"
log "Successful batches: $successful_batches"
log "Failed batches: $failed_batches"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -e "${GREEN}Successful batches: $successful_batches${NC}"
echo -e "${RED}Failed batches: $failed_batches${NC}"
echo ""
echo "📝 Full log: $LOG_FILE"
echo ""

# Check if all documents are processed
REMAINING=$(docker exec -it traceability-app python3 -c "
import sys
sys.path.append('/app')
from app.connectors.state_db_connector import StateDBConnector
from app.queries import DataloaderQueries

db = StateDBConnector()
rows = db.execute_query(DataloaderQueries.GET_INCOMPLETE_DOCUMENTS)
print(len(rows))
db.close()
" 2>/dev/null | tr -d '\r' || echo "0")

if [ "$REMAINING" -eq 0 ]; then
    echo -e "${GREEN}🎉 All documents processed successfully!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  $REMAINING documents still incomplete${NC}"
    echo "Run this script again to process remaining documents."
    exit 1
fi
