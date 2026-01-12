"""
Database Table Definitions
Defines all PostgreSQL tables for the Thar Quality Intelligence System
"""

import datetime
import logging
from sqlalchemy import (
    Table,
    MetaData,
    Column,
    Integer,
    BigInteger,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Sequence,
    Index,
    PrimaryKeyConstraint,
    ForeignKeyConstraint,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger(__name__)

metadata = MetaData()
DYNAMIC_TABLES = {}


def create_dynamic_table(name, columns, constraints=None, indexes=None):
    """
    Create a dynamic SQLAlchemy table with optional constraints and indexes.

    Args:
        name (str): The name of the table to be created.
        columns (list): A list of SQLAlchemy Column objects defining the table schema.
        constraints (list, optional): A list of SQLAlchemy constraint objects.
        indexes (list, optional): A list of SQLAlchemy index objects.

    Returns:
        Table: A SQLAlchemy Table object
    """
    logger.debug(f"Creating table '{name}' with columns: {columns}")
    table_args = columns
    if constraints:
        table_args += constraints
    if indexes:
        table_args += indexes

    table = Table(name, metadata, *table_args)
    DYNAMIC_TABLES[name] = table

    logger.debug(f"Table '{name}' created and stored in DYNAMIC_TABLES.")
    return table


# Create sequences for auto-incrementing IDs
conversation_id_seq = Sequence("conversation_id_seq")
message_id_seq = Sequence("message_id_seq")
feedback_id_seq = Sequence("feedback_id_seq")


# =====================================================
# CHAT_SESSION TABLE (stores conversation metadata)
# =====================================================
create_dynamic_table(
    "chat_session",
    [
        Column(
            "conversation_id",
            BigInteger,
            conversation_id_seq,
            primary_key=True,
            server_default=conversation_id_seq.next_value(),
        ),
        Column("user_id", BigInteger, nullable=False),
        Column("chat_title", Text, nullable=False, default="New Chat"),
        Column("chat_summary", Text, nullable=True),
        Column(
            "creation_ts", DateTime, default=datetime.datetime.utcnow, nullable=False
        ),
        Column("agent_type", Text, nullable=False, default="analyst"),
        Column(
            "is_deleted", Boolean, nullable=False, default=False, server_default="false"
        ),
    ],
    indexes=[
        Index("idx_chat_session_user_id", "user_id"),
        Index("idx_chat_session_creation_ts", "user_id", "creation_ts"),
        Index("idx_chat_session_agent_type", "user_id", "agent_type"),
    ],
)


# =====================================================
# CHAT_ENTRY TABLE (stores each message in a conversation)
# =====================================================
create_dynamic_table(
    "chat_entry",
    [
        Column(
            "message_id",
            BigInteger,
            message_id_seq,
            server_default=message_id_seq.next_value(),
            nullable=False,
        ),
        Column(
            "conversation_id",
            BigInteger,
            ForeignKey("chat_session.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("query", Text, nullable=False),
        Column("response", JSONB, nullable=False),
        Column(
            "chat_entry_ts", DateTime, default=datetime.datetime.utcnow, nullable=False
        ),
        Column("clarification_response_needed", Boolean, nullable=False, default=False),
        PrimaryKeyConstraint("conversation_id", "message_id"),
    ],
    indexes=[
        Index("idx_chat_entry_conversation_id", "conversation_id"),
    ],
)


# =====================================================
# FEEDBACK TABLE (Optional)
# =====================================================
create_dynamic_table(
    "chat_feedback",
    [
        Column(
            "feedback_id",
            BigInteger,
            feedback_id_seq,
            primary_key=True,
            server_default=feedback_id_seq.next_value(),
        ),
        Column("message_id", BigInteger, nullable=False),
        Column("conversation_id", BigInteger, nullable=False),
        Column("user_id", BigInteger, nullable=False),
        Column("feedback", Text, nullable=False),
        Column("negative_feedback_comment", Text, nullable=True),
        Column("negative_feedback_rating", Integer, nullable=True),
        Column(
            "created_at", DateTime, default=datetime.datetime.utcnow, nullable=False
        ),
        Column(
            "updated_at",
            DateTime,
            default=datetime.datetime.utcnow,
            onupdate=datetime.datetime.utcnow,
            nullable=False,
        ),
    ],
    constraints=[
        ForeignKeyConstraint(
            ["conversation_id", "message_id"],
            ["chat_entry.conversation_id", "chat_entry.message_id"],
            ondelete="CASCADE",
        )
    ],
    indexes=[
        Index("idx_feedback_user", "user_id"),
        Index("idx_feedback_message", "conversation_id", "message_id"),
    ],
)


# =====================================================
# SYSTEM_PROMPTS TABLE (stores agent prompts)
# =====================================================
prompt_id_seq = Sequence("prompt_id_seq")

create_dynamic_table(
    "system_prompts",
    [
        Column(
            "prompt_id",
            BigInteger,
            prompt_id_seq,
            primary_key=True,
            server_default=prompt_id_seq.next_value(),
        ),
        Column("prompt_key", String(100), nullable=False, unique=True),
        Column("prompt_name", String(255), nullable=False),
        Column("prompt_content", Text, nullable=False),
        Column(
            "created_at", DateTime, default=datetime.datetime.utcnow, nullable=False
        ),
        Column(
            "updated_at",
            DateTime,
            default=datetime.datetime.utcnow,
            onupdate=datetime.datetime.utcnow,
            nullable=False,
        ),
    ],
    indexes=[
        Index("idx_system_prompts_key", "prompt_key"),
    ],
)


logger.info("All table definitions created successfully")
