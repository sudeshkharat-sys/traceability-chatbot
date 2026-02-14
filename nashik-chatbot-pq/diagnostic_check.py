#!/usr/bin/env python3
"""
Diagnostic script to check OpenSearch and Postgres status for PDF embedding pipeline
Helps identify where documents are failing to process
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any

sys.path.append(str(Path(__file__).parent))

from app.connectors.state_db_connector import StateDBConnector
from app.connectors.opensearch_connector import OpenSearchConnector
from app.queries import DataloaderQueries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def check_postgres_status() -> Dict[str, Any]:
    """Check Postgres database status and document counts"""
    logger.info("\n" + "=" * 80)
    logger.info("POSTGRES DATABASE STATUS")
    logger.info("=" * 80)

    db = StateDBConnector()

    try:
        # Get status counts
        status_rows = db.execute_query(DataloaderQueries.STATUS_COUNTS)

        logger.info("\nDocument Status Counts:")
        total_docs = 0
        status_dict = {}
        for row in status_rows:
            status, count = row[0], row[1]
            status_dict[status] = count
            total_docs += count
            logger.info(f"  {status}: {count}")

        logger.info(f"\n  TOTAL: {total_docs}")

        # Get incomplete documents
        incomplete_docs = db.execute_query(DataloaderQueries.GET_INCOMPLETE_DOCUMENTS)

        if incomplete_docs:
            logger.info(f"\nIncomplete Documents ({len(incomplete_docs)}):")
            for row in incomplete_docs[:10]:  # Show first 10
                doc_id, index_name, doc_name, doc_path, doc_hash = row
                logger.info(f"  ID {doc_id}: {doc_name}")
            if len(incomplete_docs) > 10:
                logger.info(f"  ... and {len(incomplete_docs) - 10} more")

        # Get chunk counts
        chunk_count_query = "SELECT COUNT(*) FROM chunks"
        chunk_rows = db.execute_query(chunk_count_query)
        chunk_count = chunk_rows[0][0] if chunk_rows else 0

        logger.info(f"\nTotal Chunks in Postgres: {chunk_count}")

        return {
            "success": True,
            "total_documents": total_docs,
            "status_breakdown": status_dict,
            "incomplete_count": len(incomplete_docs),
            "total_chunks": chunk_count
        }

    except Exception as e:
        logger.error(f"Error checking Postgres: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def check_opensearch_status() -> Dict[str, Any]:
    """Check OpenSearch connection and index status"""
    logger.info("\n" + "=" * 80)
    logger.info("OPENSEARCH STATUS")
    logger.info("=" * 80)

    try:
        opensearch = OpenSearchConnector()

        # Test connection
        logger.info("\nTesting OpenSearch connection...")
        connection_ok = opensearch.test_connection()

        if connection_ok:
            logger.info("✓ OpenSearch connection successful")
        else:
            logger.error("✗ OpenSearch connection failed")
            return {"success": False, "error": "Connection failed"}

        # Check cluster health
        cluster_health = opensearch.client.cluster.health()
        logger.info(f"\nCluster Health:")
        logger.info(f"  Status: {cluster_health.get('status', 'unknown')}")
        logger.info(f"  Nodes: {cluster_health.get('number_of_nodes', 0)}")

        # Check index
        index_name = opensearch.index_name
        logger.info(f"\nIndex: {index_name}")

        if opensearch.index_exists():
            logger.info(f"✓ Index exists")

            # Get document count
            stats = opensearch.client.indices.stats(index=index_name)
            doc_count = stats['indices'][index_name]['total']['docs']['count']
            store_size = stats['indices'][index_name]['total']['store']['size_in_bytes']
            store_size_mb = store_size / (1024 * 1024)

            logger.info(f"  Documents: {doc_count}")
            logger.info(f"  Size: {store_size_mb:.2f} MB")

            return {
                "success": True,
                "connection": "ok",
                "cluster_status": cluster_health.get('status'),
                "index_exists": True,
                "document_count": doc_count,
                "size_mb": store_size_mb
            }
        else:
            logger.warning(f"✗ Index does not exist (will be created on first document)")
            return {
                "success": True,
                "connection": "ok",
                "cluster_status": cluster_health.get('status'),
                "index_exists": False
            }

        opensearch.close()

    except Exception as e:
        logger.error(f"Error checking OpenSearch: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def check_memory_usage():
    """Check system memory usage if psutil is available"""
    logger.info("\n" + "=" * 80)
    logger.info("SYSTEM MEMORY")
    logger.info("=" * 80)

    try:
        import psutil

        memory = psutil.virtual_memory()
        logger.info(f"\nTotal Memory: {memory.total / (1024**3):.2f} GB")
        logger.info(f"Available: {memory.available / (1024**3):.2f} GB")
        logger.info(f"Used: {memory.used / (1024**3):.2f} GB ({memory.percent}%)")
        logger.info(f"Free: {memory.free / (1024**3):.2f} GB")

    except ImportError:
        logger.info("\npsutil not available - skipping memory check")
    except Exception as e:
        logger.error(f"Error checking memory: {e}")


def main():
    """Run all diagnostic checks"""
    logger.info("\n" + "=" * 80)
    logger.info("PDF EMBEDDING PIPELINE DIAGNOSTIC CHECK")
    logger.info("=" * 80)

    # Check Postgres
    postgres_result = check_postgres_status()

    # Check OpenSearch
    opensearch_result = check_opensearch_status()

    # Check memory
    check_memory_usage()

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("=" * 80)

    if postgres_result.get("success"):
        logger.info(f"✓ Postgres: {postgres_result.get('total_documents', 0)} documents, "
                   f"{postgres_result.get('incomplete_count', 0)} incomplete, "
                   f"{postgres_result.get('total_chunks', 0)} chunks")
    else:
        logger.error(f"✗ Postgres: {postgres_result.get('error', 'Unknown error')}")

    if opensearch_result.get("success"):
        if opensearch_result.get("index_exists"):
            logger.info(f"✓ OpenSearch: {opensearch_result.get('document_count', 0)} documents, "
                       f"{opensearch_result.get('size_mb', 0):.2f} MB")
        else:
            logger.info(f"⚠ OpenSearch: Index not created yet (normal for first run)")
    else:
        logger.error(f"✗ OpenSearch: {opensearch_result.get('error', 'Unknown error')}")

    logger.info("\n" + "=" * 80)

    # Check for data mismatch
    if postgres_result.get("success") and opensearch_result.get("success"):
        pg_chunks = postgres_result.get("total_chunks", 0)
        os_docs = opensearch_result.get("document_count", 0)

        if pg_chunks != os_docs and opensearch_result.get("index_exists"):
            logger.warning(f"\n⚠ DATA MISMATCH DETECTED:")
            logger.warning(f"  Postgres has {pg_chunks} chunks")
            logger.warning(f"  OpenSearch has {os_docs} documents")
            logger.warning(f"  These should match! This suggests:")
            logger.warning(f"    - OpenSearch may have failed during upsertion")
            logger.warning(f"    - Documents were added to Postgres but not OpenSearch")
            logger.warning(f"    - Consider increasing OpenSearch memory")


if __name__ == "__main__":
    main()
