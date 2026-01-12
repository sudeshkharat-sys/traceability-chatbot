"""
Neo4j Graph Database Connector
Manages connection and query execution for automotive quality data
"""

import logging
from typing import Any, Dict, List
from langchain_neo4j import Neo4jGraph
from app.config.config import get_settings

logger = logging.getLogger(__name__)


class Neo4jConnector:
    """
    Manages Neo4j graph database connections and query execution
    """

    def __init__(self):
        """Initialize Neo4j connection"""
        self.settings = get_settings()
        self.graph = None
        self._connect()

    def _connect(self):
        """Establish connection to Neo4j database"""
        try:
            self.graph = Neo4jGraph(
                url=self.settings.NEO4J_URL,
                username=self.settings.NEO4J_USERNAME,
                password=self.settings.NEO4J_PASSWORD,
                database=self.settings.NEO4J_DATABASE,
            )
            logger.info(f"Successfully connected to Neo4j at {self.settings.NEO4J_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def execute_query(
        self, cypher_query: str, params: Dict[str, Any] = None
    ) -> List[Dict]:
        """
        Execute a Cypher query and return results

        Args:
            cypher_query: The Cypher query string
            params: Optional query parameters

        Returns:
            List of result dictionaries
        """
        try:
            logger.info(f"Executing Cypher query: {cypher_query}...")

            if params:
                results = self.graph.query(cypher_query, params=params)
            else:
                results = self.graph.query(cypher_query)

            logger.info(f"Query returned {len(results)} results")

            return results

        except Exception as e:
            logger.error(f"Error executing Cypher query: {e}")
            raise

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the graph database schema

        Returns:
            Dictionary containing schema information
        """
        try:
            schema = self.graph.get_structured_schema
            logger.info("Successfully retrieved graph schema")
            return schema
        except Exception as e:
            logger.error(f"Error retrieving schema: {e}")
            raise

    def test_connection(self) -> bool:
        """
        Test if the connection to Neo4j is working

        Returns:
            True if connection is successful
        """
        try:
            result = self.graph.query("RETURN 1 as test")
            return len(result) > 0
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_node_count(self, label: str = None) -> int:
        """
        Get count of nodes in the database

        Args:
            label: Optional node label to count specific node type

        Returns:
            Number of nodes
        """
        try:
            if label:
                query = f"MATCH (n:{label}) RETURN count(n) as count"
            else:
                query = "MATCH (n) RETURN count(n) as count"

            result = self.graph.query(query)
            return result[0]["count"] if result else 0
        except Exception as e:
            logger.error(f"Error getting node count: {e}")
            return 0

    def close(self):
        """Close the Neo4j connection"""
        if self.graph:
            try:
                # Neo4jGraph doesn't have explicit close method in langchain
                logger.info("Neo4j connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
