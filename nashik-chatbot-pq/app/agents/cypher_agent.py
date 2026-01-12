"""
Cypher Query Generation Agent
Translates natural language to Neo4j Cypher queries
"""

import logging
from typing import Dict, Any
from pydantic import BaseModel, Field

# Lazy import to avoid loading torch/transformers on every reload
# from langchain.agents import create_agent
from app.services.prompt_manager import get_cypher_prompt
from app.models.model_factory import ModelFactory
from app.connectors.neo4j_connector import Neo4jConnector

logger = logging.getLogger(__name__)


class CypherQueryResponse(BaseModel):
    """Response model for Cypher query generation"""

    cypher_query: str = Field(description="The Cypher query to execute")
    explanation: str = Field(description="Brief explanation of what the query does")


class CypherAgent:
    """
    Agent that generates Neo4j Cypher queries from natural language questions
    Uses LangChain create_agent with structured output
    """

    def __init__(self, neo4j_connector: Neo4jConnector = None):
        """
        Initialize Cypher Agent

        Args:
            neo4j_connector: Optional Neo4j connector for schema access
        """
        self.neo4j = neo4j_connector or Neo4jConnector()
        self.llm = ModelFactory.get_cypher_agent_model()
        self.agent = None
        self._initialize_agent()

    def _initialize_agent(self):
        """Initialize the LangChain agent"""
        try:
            # Lazy import to avoid loading heavy dependencies on module import
            from langchain.agents import create_agent

            # Define get_schema tool
            def get_schema() -> Dict[str, Any]:
                """Get the schema for the graph."""
                return self.neo4j.get_schema()

            # Load prompt from database (with fallback to default)
            cypher_prompt = get_cypher_prompt()

            # Create agent with structured output
            self.agent = create_agent(
                model=self.llm,
                tools=[get_schema],
                system_prompt=cypher_prompt,
                response_format=CypherQueryResponse,
                name="cypher_agent",
            )

            logger.info("Cypher agent initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing Cypher agent: {e}")
            raise

    def generate_query(self, question: str) -> Dict[str, Any]:
        """
        Generate a Cypher query from a natural language question

        Args:
            question: Natural language question

        Returns:
            Dictionary with cypher_query and explanation
        """
        try:
            logger.info(f"🔍 Cypher Agent generating query for: {question[:100]}...")

            # Invoke the agent
            result = self.agent.invoke(
                {"messages": [{"role": "user", "content": question}]}
            )

            # Extract structured response
            if "structured_response" in result:
                response = result["structured_response"]
                return {
                    "cypher_query": response.cypher_query,
                    "explanation": response.explanation,
                    "success": True,
                }
            else:
                logger.error("No structured response from agent")
                return {
                    "cypher_query": None,
                    "explanation": "Failed to generate query",
                    "success": False,
                    "error": "No structured response",
                }

        except Exception as e:
            logger.error(f"Error generating Cypher query: {e}")
            return {
                "cypher_query": None,
                "explanation": str(e),
                "success": False,
                "error": str(e),
            }

    def validate_and_generate(self, question: str) -> Dict[str, Any]:
        """
        Generate and validate a Cypher query

        Args:
            question: Natural language question

        Returns:
            Dictionary with query and validation status
        """
        result = self.generate_query(question)

        if result.get("success") and result.get("cypher_query"):
            # Basic validation
            query = result["cypher_query"]
            is_valid = self._basic_validate(query)
            result["validated"] = is_valid

            if not is_valid:
                result["warning"] = "Query may have syntax issues"

        return result

    def _basic_validate(self, query: str) -> bool:
        """
        Basic validation of Cypher query

        Args:
            query: Cypher query string

        Returns:
            True if query appears valid
        """
        try:
            if not query:
                return False

            query_upper = query.upper()

            # Check for essential keywords
            has_match = "MATCH" in query_upper or "CREATE" in query_upper
            has_return = "RETURN" in query_upper

            # Check for LIMIT (should be present for safety)
            has_limit = "LIMIT" in query_upper

            return (has_match or has_return) and has_limit

        except Exception:
            return False
