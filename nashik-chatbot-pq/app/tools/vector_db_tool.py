"""
Vector DB Search Tool
Searches the OpenSearch vector store for standards and guidelines documents.
"""

import logging
import json
from langchain_core.tools import tool

from app.connectors.opensearch_connector import OpenSearchConnector

logger = logging.getLogger(__name__)


@tool
def search_standards(query: str, top_k: int = 5) -> str:
    """
    Search the Standards & Guidelines vector database for documents relevant to the query.

    Use this tool whenever the user asks a question about standards, guidelines,
    policies, procedures, or any reference documents that have been ingested.

    Args:
        query: The search question or topic to look up in the knowledge base.
        top_k: Number of most-relevant document chunks to retrieve (default 5, max 10).

    Returns:
        A JSON string containing the matched document chunks with their
        relevance scores and metadata (source file, section, etc.).
    """
    try:
        # Clamp top_k between 1 and 10
        top_k = max(1, min(top_k, 10))

        connector = OpenSearchConnector()
        results = connector.similarity_search_with_score(query=query, k=top_k)
        connector.close()

        if not results:
            return json.dumps({"found": False, "message": "No relevant documents found for this query."})

        formatted = []
        for rank, (doc, score) in enumerate(results, start=1):
            formatted.append({
                "rank": rank,
                "relevance_score": round(score, 4),
                "content": doc["text"],
                "metadata": doc.get("metadata", {}),
            })

        logger.info(f"search_standards: returned {len(formatted)} chunks for query '{query[:80]}…'")

        return json.dumps({"found": True, "count": len(formatted), "results": formatted})

    except Exception as e:
        logger.error(f"search_standards error: {e}", exc_info=True)
        return json.dumps({"found": False, "error": str(e)})
