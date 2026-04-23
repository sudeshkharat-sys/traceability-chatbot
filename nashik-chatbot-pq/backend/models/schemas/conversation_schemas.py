"""
Pydantic schemas for conversation API
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class InitiateConversationDto(BaseModel):
    """Request model for initiating a new conversation"""
    user_id: int
    agent_type: Optional[str] = "analyst"


class InitiateConversationResponseDto(BaseModel):
    """Response model for a newly initiated conversation"""
    conversation_id: int = Field(alias="conversationId")
    initial_message: str = "Chat session started."

    class Config:
        populate_by_name = True


class ConversationDto(BaseModel):
    """Request model for sending a message in a conversation"""
    user_id: int
    user_message: str
    agent_type: Optional[str] = "analyst"


class ConversationResponseDto(BaseModel):
    """Response model for a conversation message"""
    messageId: int
    chat_response: Dict
    timestamp: str = ""
    needs_clarification: Optional[bool] = False


class FeedbackDto(BaseModel):
    """Data model for user feedback on conversations"""
    user_id: int
    feedback: str
    negative_feedback_comment: Optional[str] = None


class ChatListItemDto(BaseModel):
    """Single chat item in list"""
    conversation_id: int
    chat_title: str
    creation_ts: str
    agent_type: str


class ChatHistoryResponseDto(BaseModel):
    """Response model for chat history"""
    response: List[ChatListItemDto]


class CompleteChatDto(BaseModel):
    """Complete chat with all messages"""
    conversation_id: int
    user_id: int
    chat_title: str
    chat_summary: Optional[str]
    creation_ts: str
    agent_type: str
    query_responses: List[Dict]

