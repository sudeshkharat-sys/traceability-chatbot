#!/usr/bin/env python3
"""
Debug script to check PDF processing status and identify why processing stopped
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from app.connectors.state_db_connector import StateDBConnector
from app.queries import DataloaderQueries

def main():
    db = StateDBConnector()

    print("=" * 80)
    print("PDF Processing Status Report")
    print("=" * 80)

    # 1. Overall status counts
    print("\n📊 Overall Status:")
    query = "SELECT status, COUNT(*) as count FROM scraped_docs GROUP BY status ORDER BY status;"
    results = db.execute_query(query)
    for row in results:
        status, count = row
        print(f"  {status}: {count} documents")

    # 2. Last 10 completed documents
    print("\n✅ Last 10 Completed Documents:")
    query = """
        SELECT id, doc_name, updated_at
        FROM scraped_docs
        WHERE status = 'complete'
        ORDER BY updated_at DESC
        LIMIT 10;
    """
    results = db.execute_query(query)
    for row in results:
        doc_id, name, updated = row
        print(f"  #{doc_id}: {name} (completed: {updated})")

    # 3. Next 10 incomplete documents
    print("\n⏳ Next 10 Incomplete Documents:")
    query = """
        SELECT id, doc_name, status, created_at
        FROM scraped_docs
        WHERE status = 'incomplete'
        ORDER BY id
        LIMIT 10;
    """
    results = db.execute_query(query)
    for row in results:
        doc_id, name, status, created = row
        print(f"  #{doc_id}: {name} (status: {status})")

    # 4. Check for any error patterns
    print("\n🔍 Checking for Patterns:")
    query = "SELECT COUNT(*) FROM scraped_docs WHERE status = 'incomplete';"
    incomplete_count = db.execute_query(query)[0][0]
    print(f"  Total incomplete documents: {incomplete_count}")

    query = "SELECT MIN(id), MAX(id) FROM scraped_docs WHERE status = 'complete';"
    result = db.execute_query(query)[0]
    if result[0] and result[1]:
        print(f"  Completed document ID range: {result[0]} - {result[1]}")

    query = "SELECT MIN(id), MAX(id) FROM scraped_docs WHERE status = 'incomplete';"
    result = db.execute_query(query)[0]
    if result[0] and result[1]:
        print(f"  Incomplete document ID range: {result[0]} - {result[1]}")

    # 5. Chunk statistics
    print("\n📦 Chunk Statistics:")
    query = """
        SELECT
            COUNT(DISTINCT document_id) as docs_with_chunks,
            COUNT(*) as total_chunks,
            AVG(LENGTH(chunk_text)) as avg_chunk_size
        FROM document_chunks;
    """
    results = db.execute_query(query)
    for row in results:
        docs, total, avg_size = row
        print(f"  Documents with chunks: {docs}")
        print(f"  Total chunks created: {total}")
        print(f"  Average chunk size: {avg_size:.0f} characters")

    print("\n" + "=" * 80)

    db.close()

if __name__ == "__main__":
    main()
