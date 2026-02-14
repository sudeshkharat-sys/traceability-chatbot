#!/bin/bash
# Process PDFs in batches to prevent OOM
# Each batch processes 5 PDFs, then restarts the container to clear memory

set -e

BATCH_SIZE=5
MAX_ITERATIONS=50  # Safety limit to prevent infinite loops

echo "Starting batch PDF processing..."
echo "Batch size: $BATCH_SIZE PDFs per batch"
echo "=========================================="

for i in $(seq 1 $MAX_ITERATIONS); do
    echo ""
    echo "=== Batch $i starting ==="

    # Check how many incomplete docs remain
    INCOMPLETE=$(docker exec -it traceability-postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT COUNT(*) FROM scraped_docs WHERE status = 'incomplete';" | tr -d ' \r')

    echo "Incomplete PDFs remaining: $INCOMPLETE"

    # If no incomplete docs, we're done!
    if [ "$INCOMPLETE" -eq 0 ] || [ "$INCOMPLETE" = "" ]; then
        echo "✅ All PDFs processed!"
        break
    fi

    # Process one batch
    echo "Processing batch of $BATCH_SIZE PDFs..."
    docker exec -e BATCH_SIZE=$BATCH_SIZE -it traceability-app python -m dataloader.document_embedding_processor || {
        echo "⚠️  Batch $i had errors, continuing to next batch..."
    }

    # Restart app container to clear memory
    echo "Restarting app container to clear memory..."
    docker compose restart app

    # Wait for app to be healthy
    echo "Waiting for app to be ready..."
    sleep 30

    # Check if app is healthy
    docker exec traceability-app curl -f http://localhost:5000/health || {
        echo "⚠️  App health check failed, waiting longer..."
        sleep 30
    }

    echo "=== Batch $i complete ==="
done

echo ""
echo "=========================================="
echo "Batch processing complete!"
echo "Running final status check..."
docker exec -it traceability-app python debug_processing_status.py
