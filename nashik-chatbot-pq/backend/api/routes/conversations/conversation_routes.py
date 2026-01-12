"""
Conversation API Routes
Handles HTTP and WebSocket endpoints for conversations
"""

import logging
import json
import asyncio
from fastapi import (
    APIRouter,
    HTTPException,
    Path,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse
from backend.models.schemas.conversation_schemas import (
    ConversationDto,
    InitiateConversationDto,
    InitiateConversationResponseDto,
    FeedbackDto,
)
from backend.services.conversations.conversation_service import ConversationService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversations"])

# Lazy-loaded service instance (created on first use, after database initialization)
_conversation_service = None


def get_conversation_service() -> ConversationService:
    """
    Get the conversation service instance (lazy initialization).
    This ensures the service is only created after the database is ready.
    """
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service


@router.post("/initiate", response_model=InitiateConversationResponseDto)
async def initiate_conversation(payload: InitiateConversationDto):
    """
    Initiate a new conversation

    Args:
        payload: Request with user_id and agent_type

    Returns:
        Conversation ID and initial message
    """
    try:
        agent_type = payload.agent_type or "analyst"

        conversation_id = get_conversation_service().start_new_chat(payload, agent_type)

        result = {
            "conversationId": conversation_id,
            "initial_message": "Chat session started.",
        }

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        logger.error(f"Error initiating conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initiate conversation")


@router.post("/{conversation_id}/messages/{message_id}/feedback")
async def submit_feedback(
    conversation_id: int = Path(..., description="Unique conversation identifier"),
    message_id: int = Path(..., description="Unique message identifier"),
    payload: FeedbackDto = None,
):
    """
    Submit feedback for a message

    Args:
        conversation_id: Conversation ID
        message_id: Message ID
        payload: Feedback data

    Returns:
        Feedback confirmation
    """
    try:
        feedback_id = get_conversation_service().upsert_feedback(
            conversation_id, message_id, payload
        )

        result = {
            "status": "SUCCESS",
            "data": {
                "feedbackId": feedback_id,
                "feedback": payload.feedback,
                "messageId": message_id,
            },
        }

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit feedback")


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: int = Path(..., description="Unique conversation identifier"),
):
    """
    Get complete conversation history

    Args:
        conversation_id: Conversation ID

    Returns:
        Complete conversation with all messages
    """
    try:
        response = get_conversation_service().get_complete_chat(conversation_id)
        return JSONResponse({"response": response})

    except Exception as e:
        logger.error(f"Error retrieving conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve conversation")


@router.get("/user/{user_id}/history")
async def get_conversation_history(
    user_id: int = Path(..., description="Unique user identifier"),
    agent_type: str = Query("analyst", description="Agent type filter"),
):
    """
    Get conversation history for a user

    Args:
        user_id: User ID
        agent_type: Filter by agent type ('analyst' or 'cypher')

    Returns:
        List of user's conversations
    """
    try:
        response = get_conversation_service().list_chats(user_id, agent_type)
        return JSONResponse({"response": response})

    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve conversation history"
        )


@router.websocket("/{conversation_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: int = Path(..., description="Unique conversation identifier"),
):
    """
    WebSocket endpoint for streaming conversation responses

    Args:
        websocket: WebSocket connection
        conversation_id: Conversation ID
    """
    await websocket.accept()

    try:
        # Receive message
        data = await websocket.receive_text()

        try:
            payload_data = json.loads(data)

            agent_type = payload_data.get("agent_type", "analyst")

            # Validate agent type
            if agent_type not in ["analyst", "cypher"]:
                await websocket.send_json(
                    {
                        "type": "error",
                        "content": f"Invalid agent type: {agent_type}. Must be 'analyst' or 'cypher'.",
                    }
                )
                return

            # Create payload
            payload = ConversationDto(
                user_id=payload_data.get("user_id", 1),  # Default user for now
                user_message=payload_data.get("user_message"),
                agent_type=agent_type,
            )

            if not payload.user_message:
                await websocket.send_json(
                    {"type": "error", "content": "User message is required"}
                )
                return

            # Send initialization message
            await websocket.send_json(
                {
                    "type": "thinking",
                    "step": "initialization",
                    "content": f"Processing your query with {agent_type.upper()} agent...",
                }
            )

            # Stream responses
            for event_str in get_conversation_service().process_streaming(
                conversation_id, payload, agent_type
            ):
                if event_str.startswith("data: "):
                    json_str = event_str[6:].strip()
                    await websocket.send_text(json_str)
                    await asyncio.sleep(0.01)  # Small delay for smooth streaming

        except json.JSONDecodeError:
            await websocket.send_json(
                {"type": "error", "content": "Invalid message format"}
            )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for conversation {conversation_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
            await asyncio.sleep(0.1)  # Give time for error to be sent
        except:
            pass

    finally:
        try:
            await websocket.close()
        except:
            pass


@router.delete("/delete/{conversation_id}")
async def delete_conversation(
    conversation_id: int = Path(..., description="Unique conversation identifier"),
):
    """
    Soft delete a conversation

    Args:
        conversation_id: Conversation ID

    Returns:
        Deletion confirmation
    """
    try:
        success = get_conversation_service().delete_chat(conversation_id)

        if success:
            return JSONResponse(
                {
                    "message": "Conversation deleted successfully",
                    "conversation_id": conversation_id,
                }
            )
        else:
            raise HTTPException(status_code=404, detail="Conversation not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete conversation")
