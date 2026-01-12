"""
Query Executor
Executes Cypher queries on Neo4j with error handling and formatting
"""

import logging
from typing import Dict, List, Any
from app.connectors.neo4j_connector import Neo4jConnector

logger = logging.getLogger(__name__)


class QueryExecutor:
    """
    Executes and manages Cypher query execution
    """

    def __init__(
        self, neo4j_connector: Neo4jConnector = None, max_full_records: int = 30
    ):
        """
        Initialize QueryExecutor

        Args:
            neo4j_connector: Optional Neo4j connector instance
            max_full_records: Max records to return in full before summarizing (default: 30)
        """
        self.neo4j = neo4j_connector or Neo4jConnector()
        self.max_full_records = max_full_records

    def _summarize_large_results(
        self, records: List[Dict], max_records: int
    ) -> Dict[str, Any]:
        """
        Intelligently summarize large result sets for LLM processing

        Args:
            records: Full list of records
            max_records: Maximum records to return in full

        Returns:
            Dictionary with summarized data
        """
        total_count = len(records)

        if total_count <= max_records:
            return {"records": records, "count": total_count, "summarized": False}

        # Return first N records + summary statistics
        sample_records = records[:max_records]

        # Generate summary stats
        summary = {
            "total_records": total_count,
            "showing": max_records,
            "remaining": total_count - max_records,
            "note": f"Showing top {max_records} of {total_count} results for faster response",
        }

        logger.info(
            f"Summarized {total_count} records to {max_records} for LLM processing"
        )

        return {
            "records": sample_records,
            "count": total_count,
            "summarized": True,
            "summary": summary,
        }

    def execute_cypher(
        self, cypher_query: str, params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a Cypher query and return formatted results
        Automatically summarizes large result sets for faster LLM processing

        Args:
            cypher_query: The Cypher query to execute
            params: Optional query parameters

        Returns:
            Dictionary containing query, records, and metadata
        """
        try:
            logger.info("Executing Cypher query")

            # Execute the query
            result_data = self.neo4j.execute_query(cypher_query, params)

            # Intelligently summarize if too many records
            # result_data = self._summarize_large_results(
            #     all_records, self.max_full_records
            # )

            # Format response
            response = {
                "query": cypher_query,
                "records": result_data,
                "count": len(result_data),
                "success": True,
            }

            logger.info(
                f"Query executed successfully, returned {len(result_data)} records"
            )

            return response

        except Exception as e:
            logger.error(f"Error executing Cypher query: {e}")
            return {
                "query": cypher_query,
                "records": [],
                "count": 0,
                "success": False,
                "error": str(e),
            }

    def execute_with_timeout(
        self,
        cypher_query: str,
        timeout_seconds: int = 30,
        params: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute query with timeout

        Args:
            cypher_query: The Cypher query to execute
            timeout_seconds: Timeout in seconds
            params: Optional query parameters

        Returns:
            Dictionary containing query results
        """
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError(f"Query exceeded {timeout_seconds} seconds timeout")

        try:
            # Set up timeout (Unix-based systems)
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)

            result = self.execute_cypher(cypher_query, params)

            # Cancel timeout
            signal.alarm(0)

            return result

        except TimeoutError as e:
            logger.error(f"Query timeout: {e}")
            return {
                "query": cypher_query,
                "records": [],
                "count": 0,
                "success": False,
                "error": f"Query timeout after {timeout_seconds} seconds",
            }
        except Exception as e:
            # Cancel timeout
            signal.alarm(0)
            logger.error(f"Error in query execution: {e}")
            return {
                "query": cypher_query,
                "records": [],
                "count": 0,
                "success": False,
                "error": str(e),
            }

    def validate_query(self, cypher_query: str) -> bool:
        """
        Basic validation of Cypher query syntax

        Args:
            cypher_query: The Cypher query to validate

        Returns:
            True if query appears valid
        """
        try:
            # Basic checks
            if not cypher_query or not isinstance(cypher_query, str):
                return False

            # Check for essential Cypher keywords
            query_upper = cypher_query.upper()
            has_match = "MATCH" in query_upper
            has_return = "RETURN" in query_upper

            return has_match or has_return

        except Exception as e:
            logger.error(f"Error validating query: {e}")
            return False

    def format_results_for_display(self, results: List[Dict]) -> str:
        """
        Format query results for human-readable display

        Args:
            results: List of query result dictionaries

        Returns:
            Formatted string representation
        """
        try:
            if not results:
                return "No results found"

            # Get column names from first record
            if len(results) > 0:
                columns = list(results[0].keys())

                # Create formatted output
                output = []
                output.append(f"Results: {len(results)} records")
                output.append("-" * 80)

                for i, record in enumerate(results[:20], 1):  # Limit to 20 for display
                    output.append(f"\nRecord {i}:")
                    for col in columns:
                        value = record.get(col)
                        output.append(f"  {col}: {value}")

                if len(results) > 20:
                    output.append(f"\n... and {len(results) - 20} more records")

                return "\n".join(output)

            return str(results)

        except Exception as e:
            logger.error(f"Error formatting results: {e}")
            return str(results)
