"""
Conversation Service
Orchestrates conversation flow, agent execution, and chat history
"""

import logging
import json
from typing import Dict, Any, Generator
from datetime import datetime
from app.chat_history.chat_manager import ChatManager
from app.connectors.state_db_connector import StateDBConnector

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Service class for handling conversation flow and agent orchestration.

    Neo4jConnector and AgentPool are initialised lazily — only when the
    first message is actually sent (process_streaming).  This keeps the
    chat-history endpoints fast because they only need PostgreSQL.
    """

    def __init__(self):
        """Initialize the ConversationService (lightweight — PostgreSQL only)"""
        self.state_db = StateDBConnector()
        self.chat_manager = ChatManager(self.state_db)

        # Heavy deps — created on first use via _get_agent_pool()
        self._neo4j = None
        self._agent_pool = None
        logger.info("ConversationService initialized (lightweight)")

    def _get_agent_pool(self):
        """Lazy-init Neo4j + AgentPool on first use (heavy imports)."""
        if self._agent_pool is None:
            from app.connectors.neo4j_connector import Neo4jConnector
            from app.agents.agent_pool import AgentPool

            logger.info("Initializing Neo4j + AgentPool (first message)...")
            self._neo4j = Neo4jConnector()
            self._agent_pool = AgentPool(self._neo4j)
            logger.info("Neo4j + AgentPool ready")
        return self._agent_pool

    def start_new_chat(self, payload, agent_type: str = "analyst") -> int:
        """
        Start a new chat session and return the conversation ID

        Args:
            payload: Request payload containing user_id and page_context
            agent_type: Type of agent ('analyst' or 'cypher')

        Returns:
            conversation_id
        """
        try:
            user_id = payload.user_id
            chat_title = f"New Chat - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            conversation_id = self.chat_manager.create_conversation(
                user_id=user_id, chat_title=chat_title, agent_type=agent_type
            )

            logger.info(f"Started new {agent_type} chat: {conversation_id}")
            return conversation_id

        except Exception as e:
            logger.error(f"Error starting new chat: {e}")
            raise

    def process_streaming(
        self, conversation_id: int, payload, agent_type: str = "analyst"
    ) -> Generator[str, None, None]:
        """
        Stream the processing of a query through the specified agent

        Args:
            conversation_id: Unique identifier for the chat session
            payload: The request payload containing user message
            agent_type: Agent type to use ('analyst' or 'cypher')

        Yields:
            JSON-formatted string events for streaming
        """
        try:
            if not payload.user_message:
                yield json.dumps(
                    {"type": "error", "content": "User message is required"}
                ) + "\n\n"
                return

            full_response = []
            chart_data = None
            citations_data = []
            response_saved = False

            # Get agent from pool (lazy-inits Neo4j + AgentPool on first call)
            with self._get_agent_pool().get_agent(conversation_id, agent_type) as agent:
                logger.info(
                    f"Using {agent_type} agent for conversation {conversation_id}"
                )

                # Stream agent responses
                for event in agent.stream(user_question=payload.user_message):
                    # Send event to client
                    yield f"data: {json.dumps(event)}\n\n"

                    # Collect response tokens
                    if event.get("type") == "token":
                        full_response.append(event["content"])

                    # Collect chart data if present
                    elif event.get("type") == "chart":
                        chart_data = event.get("chart_data")
                        logger.info(f"Captured chart data: {chart_data.get('type') if chart_data else None}")
                        
                    # Collect citations if present
                    elif event.get("type") == "citations":
                        citations_data = event.get("citations", [])
                        logger.info(f"Captured {len(citations_data)} citations")

                # Save response to database after streaming completes
                if full_response:
                    complete_response = "".join(full_response)
                    print(complete_response)
                    response_data = {
                        "response": complete_response,
                        "similar_docs": citations_data if citations_data else [],
                    }

                    # Include chart data if available
                    if chart_data:
                        response_data["chart_data"] = chart_data

                    message_id = self.chat_manager.save_message(
                        conversation_id=conversation_id,
                        query=payload.user_message,
                        response=response_data,
                        clarification_needed=False,
                    )

                    # Update chat title if first message
                    messages = self.chat_manager.get_conversation_messages(
                        conversation_id
                    )
                    if len(messages) == 1:
                        title = payload.user_message[:50] + (
                            "..." if len(payload.user_message) > 50 else ""
                        )
                        self.chat_manager.update_chat_title(conversation_id, title)

                    # Send final response with message ID and chart data
                    final_data = {
                        "type": "final",
                        "content": complete_response,
                        "messageId": message_id,
                        "response": complete_response,
                        "citations": citations_data if citations_data else []
                    }

                    # Include chart data in final response
                    if chart_data:
                        final_data["chart_data"] = chart_data

                    yield f"data: {json.dumps(final_data)}\n\n"

                    logger.info(
                        f"Saved message {message_id} to conversation {conversation_id}"
                    )

        except Exception as e:
            logger.error(f"Error in process_streaming: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {str(e)}'})}\n\n"

    def get_complete_chat(self, conversation_id: int) -> Dict:
        """
        Retrieve the complete chat history for a given chat session

        Args:
            conversation_id: The ID of the chat session

        Returns:
            Complete chat history dictionary
        """
        try:
            complete_chat = self.chat_manager.get_complete_chat(conversation_id)
            logger.debug(f"Retrieved complete chat for {conversation_id}")
            return complete_chat
        except Exception as e:
            logger.error(f"Error retrieving complete chat: {e}", exc_info=True)
            return {}

    def list_chats(self, user_id: int, agent_type: str = "analyst") -> list:
        """
        List all chat sessions for a given user, filtered by agent type

        Args:
            user_id: The ID of the user
            agent_type: Agent type filter ('analyst' or 'cypher')

        Returns:
            List of chat sessions with metadata
        """
        try:
            chats = self.chat_manager.list_user_chats(user_id, agent_type)
            logger.info(
                f"Listed {len(chats)} chats for user {user_id} (type: {agent_type})"
            )
            return chats
        except Exception as e:
            logger.error(f"Error listing chats: {e}", exc_info=True)
            return []

    def delete_chat(self, conversation_id: int) -> bool:
        """
        Delete a conversation (soft delete)

        Args:
            conversation_id: The ID of the conversation to delete

        Returns:
            True if deletion was successful
        """
        try:
            success = self.chat_manager.delete_chat(conversation_id)
            if success:
                logger.info(f"Successfully deleted conversation {conversation_id}")
            else:
                logger.warning(f"Failed to delete conversation {conversation_id}")
            return success
        except Exception as e:
            logger.error(f"Error deleting conversation: {e}", exc_info=True)
            return False

    def upsert_feedback(self, conversation_id: int, message_id: int, payload) -> str:
        """
        Create or update feedback for a specific chat entry
        (Placeholder for future feedback implementation)

        Args:
            conversation_id: The unique identifier for the conversation
            message_id: The unique identifier for the message
            payload: Feedback data

        Returns:
            Feedback ID
        """
        try:
            # TODO: Implement feedback storage
            logger.info(
                f"Feedback received for message {message_id} in conversation {conversation_id}"
            )
            return "feedback_placeholder"
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            raise
