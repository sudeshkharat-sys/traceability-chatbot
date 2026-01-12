"""
Agent Pool
Manages agent lifecycle and provides agent instances
"""

import logging
from contextlib import contextmanager
from typing import Optional
from app.agents.cypher_agent import CypherAgent
from app.agents.analyst_agent import AnalystAgent
from app.agents.checkpointer_manager import get_checkpointer_manager
from app.connectors.neo4j_connector import Neo4jConnector

logger = logging.getLogger(__name__)


class AgentPool:
    """
    Manages pool of agents for different conversation types
    Provides context manager for agent lifecycle
    """

    def __init__(self, neo4j_connector: Neo4jConnector = None):
        """
        Initialize Agent Pool

        Args:
            neo4j_connector: Optional shared Neo4j connector
        """
        self.neo4j = neo4j_connector or Neo4jConnector()
        self._active_agents = {}

        # Initialize checkpointer manager for conversation memory
        self.checkpointer_manager = get_checkpointer_manager()
        self.checkpointer = self.checkpointer_manager.get_checkpointer()

        if self.checkpointer:
            logger.info("🧠 Agent pool initialized with PostgreSQL conversation memory")
        else:
            logger.warning(
                "⚠️  Agent pool initialized without persistent memory. "
                "Conversations will not persist across sessions."
            )

    @contextmanager
    def get_agent(self, conversation_id: int, agent_type: str = "analyst", **kwargs):
        """
        Get an agent instance with context management

        Args:
            conversation_id: Unique conversation identifier
            agent_type: Type of agent ('cypher' or 'analyst')
            **kwargs: Additional arguments for agent initialization

        Yields:
            Agent instance
        """
        agent_key = f"{conversation_id}_{agent_type}"

        try:
            # Create agent instance
            if agent_type == "cypher":
                agent = CypherAgent(neo4j_connector=self.neo4j)
            elif agent_type == "analyst":
                # Pass conversation_id as thread_id for conversation tracking
                thread_id = f"conv_{conversation_id}"
                agent = AnalystAgent(
                    neo4j_connector=self.neo4j,
                    thread_id=thread_id,
                    checkpointer=self.checkpointer,  # Enable conversation memory
                )
            else:
                raise ValueError(f"Unknown agent type: {agent_type}")

            self._active_agents[agent_key] = agent
            emoji = "🔍" if agent_type == "cypher" else "📝"
            logger.info(
                f"{emoji} Created {agent_type.upper()} agent for conversation {conversation_id}"
            )

            yield agent

        finally:
            # Cleanup
            if agent_key in self._active_agents:
                del self._active_agents[agent_key]
                logger.info(
                    f"Released {agent_type} agent for conversation {conversation_id}"
                )

    def get_cypher_agent(self) -> CypherAgent:
        """
        Get a standalone Cypher agent instance

        Returns:
            CypherAgent instance
        """
        return CypherAgent(neo4j_connector=self.neo4j)

    def get_analyst_agent(self, thread_id: str = "default") -> AnalystAgent:
        """
        Get a standalone Analyst agent instance

        Args:
            thread_id: Thread ID for conversation tracking

        Returns:
            AnalystAgent instance
        """
        return AnalystAgent(
            neo4j_connector=self.neo4j,
            thread_id=thread_id,
            checkpointer=self.checkpointer,  # Enable conversation memory
        )

    def get_active_agent_count(self) -> int:
        """
        Get number of currently active agents

        Returns:
            Count of active agents
        """
        return len(self._active_agents)

    def cleanup_all(self):
        """Cleanup all active agents"""
        logger.info(f"Cleaning up {len(self._active_agents)} active agents")
        self._active_agents.clear()

    def close(self):
        """
        Close agent pool and cleanup resources including checkpointer
        Call this during application shutdown
        """
        self.cleanup_all()
        if self.checkpointer_manager:
            self.checkpointer_manager.close()
            logger.info("Closed checkpointer manager")
