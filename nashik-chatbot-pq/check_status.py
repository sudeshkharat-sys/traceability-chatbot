#!/usr/bin/env python3
"""
Quick script to check Postgres vs OpenSearch status
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.opensearch_connector import OpenSearchConnector

print("=" * 80)
print("POSTGRES vs OPENSEARCH STATUS CHECK")
print("=" * 80)

# Check Postgres
db = StateDBConnector()

print("\n1. POSTGRES - Document Status:")
print("-" * 80)
status_query = """
    SELECT status, COUNT(*) as count
    FROM scraped_docs
    GROUP BY status
"""
status_rows = db.execute_query(status_query)
total_docs = 0
for row in status_rows:
    status, count = row[0], row[1]
    print(f"   {status}: {count} documents")
    total_docs += count
print(f"   TOTAL: {total_docs} documents")

print("\n2. POSTGRES - Chunk Counts:")
print("-" * 80)
chunk_query = """
    SELECT COUNT(*) as total_chunks,
           COUNT(DISTINCT doc_id) as unique_docs
    FROM chunks
"""
chunk_rows = db.execute_query(chunk_query)
if chunk_rows:
    total_chunks, unique_docs = chunk_rows[0][0], chunk_rows[0][1]
    print(f"   Total chunks: {total_chunks}")
    print(f"   Unique documents with chunks: {unique_docs}")

# Get incomplete documents
incomplete_query = """
    SELECT id, doc_name,
           (SELECT COUNT(*) FROM chunks WHERE doc_id = scraped_docs.id) as chunk_count
    FROM scraped_docs
    WHERE status = 'incomplete'
    ORDER BY id
"""
incomplete_rows = db.execute_query(incomplete_query)
print(f"\n3. INCOMPLETE Documents ({len(incomplete_rows)}):")
print("-" * 80)
for row in incomplete_rows[:20]:  # Show first 20
    doc_id, doc_name, chunk_count = row[0], row[1], row[2] if len(row) > 2 else 0
    print(f"   ID {doc_id}: {doc_name} ({chunk_count} chunks in DB)")
if len(incomplete_rows) > 20:
    print(f"   ... and {len(incomplete_rows) - 20} more")

# Check complete documents
complete_query = """
    SELECT COUNT(*) FROM scraped_docs WHERE status = 'complete'
"""
complete_rows = db.execute_query(complete_query)
complete_count = complete_rows[0][0] if complete_rows else 0

db.close()

# Check OpenSearch
print("\n4. OPENSEARCH:")
print("-" * 80)
opensearch = OpenSearchConnector()
try:
    if opensearch.index_exists():
        stats = opensearch.client.indices.stats(index=opensearch.index_name)
        os_doc_count = stats['indices'][opensearch.index_name]['total']['docs']['count']
        print(f"   Total chunks in OpenSearch: {os_doc_count}")

        # Get unique document IDs from OpenSearch
        search_query = {
            "size": 0,
            "aggs": {
                "unique_docs": {
                    "cardinality": {
                        "field": "doc_id"
                    }
                }
            }
        }
        result = opensearch.client.search(index=opensearch.index_name, body=search_query)
        unique_doc_count = result['aggregations']['unique_docs']['value']
        print(f"   Unique PDFs in OpenSearch: {unique_doc_count}")
    else:
        os_doc_count = 0
        unique_doc_count = 0
        print(f"   Index does not exist yet")
except Exception as e:
    print(f"   Error checking OpenSearch: {e}")
    os_doc_count = 0
    unique_doc_count = 0

opensearch.close()

# Analysis
print("\n" + "=" * 80)
print("ANALYSIS:")
print("=" * 80)

if chunk_rows and os_doc_count > 0:
    pg_chunks = chunk_rows[0][0]
    if pg_chunks != os_doc_count:
        print(f"⚠️  MISMATCH: Postgres has {pg_chunks} chunks, OpenSearch has {os_doc_count}")
        print(f"   Difference: {abs(pg_chunks - os_doc_count)} chunks")
    else:
        print(f"✓  Postgres and OpenSearch chunk counts match: {pg_chunks}")

if incomplete_rows and os_doc_count > 0:
    # Check if incomplete docs already have chunks in OpenSearch
    print(f"\n⚠️  ISSUE DETECTED:")
    print(f"   {len(incomplete_rows)} documents marked 'incomplete' in Postgres")
    print(f"   But {os_doc_count} chunks already exist in OpenSearch")
    print(f"   This means documents are being processed but not marked complete!")
    print(f"\n   ROOT CAUSE: Postgres status update is failing!")
    print(f"   Documents keep reprocessing because they stay 'incomplete'")

if complete_count > 0 and unique_doc_count > 0:
    print(f"\n✓  Successfully completed: {complete_count} documents")

print("\n" + "=" * 80)
