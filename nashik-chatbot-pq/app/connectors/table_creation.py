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
    Float,
    text,
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
scraped_doc_id_seq = Sequence("scraped_doc_id_seq")
chunk_id_seq = Sequence("chunk_id_seq")
user_id_seq = Sequence("user_id_seq")
image_id_seq = Sequence("image_id_seq")
label_id_seq = Sequence("label_id_seq")
warranty_id_seq = Sequence("warranty_id_seq")
raw_warranty_id_seq = Sequence("raw_warranty_id_seq")



# =====================================================
# USERS TABLE (stores user accounts for login/signup)
# =====================================================
create_dynamic_table(
    "users",
    [
        Column(
            "user_id",
            BigInteger,
            user_id_seq,
            primary_key=True,
            server_default=user_id_seq.next_value(),
        ),
        Column("username", String(100), nullable=False, unique=True),
        Column("first_name", String(100), nullable=False),
        Column("last_name", String(100), nullable=False),
        Column("email", String(255), nullable=False, unique=True),
        Column("password_hash", String(255), nullable=False),
        Column(
            "created_at", DateTime, default=datetime.datetime.utcnow, nullable=False
        ),
    ],
    indexes=[
        Index("idx_users_username", "username"),
        Index("idx_users_email", "email"),
    ],
)


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


# =====================================================
# SCRAPED_DOCS TABLE (tracks documents to be processed)
# =====================================================
create_dynamic_table(
    "scraped_docs",
    [
        Column(
            "id",
            BigInteger,
            scraped_doc_id_seq,
            primary_key=True,
            server_default=scraped_doc_id_seq.next_value(),
        ),
        Column("index_name", String(255), nullable=False),
        Column("doc_name", Text, nullable=False),
        Column("doc_path", Text, nullable=False),
        Column("doc_hash", String(64), nullable=False),
        Column("status", String(20), nullable=False, default="incomplete"),
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
        Index("idx_scraped_docs_status", "status"),
        Index("idx_scraped_docs_index_name", "index_name"),
        Index("idx_scraped_docs_hash", "doc_hash"),
    ],
)


# =====================================================
# CHUNKS TABLE (stores processed document chunks)
# =====================================================
create_dynamic_table(
    "chunks",
    [
        Column(
            "chunk_id",
            BigInteger,
            chunk_id_seq,
            primary_key=True,
            server_default=chunk_id_seq.next_value(),
        ),
        Column(
            "doc_id",
            BigInteger,
            ForeignKey("scraped_docs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("index_name", String(255), nullable=False),
        Column("chunk_hash", String(64), nullable=False),
        Column("chunk_text", Text, nullable=False),
        Column("chunk_metadata", JSONB, nullable=True),
        Column("opensearch_id", String(255), nullable=True),
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
        Index("idx_chunks_doc_id", "doc_id"),
        Index("idx_chunks_index_name", "index_name"),
        Index("idx_chunks_hash", "chunk_hash"),
        Index("idx_chunks_opensearch_id", "opensearch_id"),
    ],
)

# =====================================================
# RAW_WARRANTY_DATA TABLE (PartLabeler)
# =====================================================
create_dynamic_table(
    "raw_warranty_data",
    [
        Column(
            "id",
            BigInteger,
            raw_warranty_id_seq,
            primary_key=True,
            server_default=raw_warranty_id_seq.next_value(),
        ),
        Column("region", Text),
        Column("zone", Text),
        Column("area_office", Text),
        Column("plant", Text),
        Column("plant_desc", Text),
        Column("commodity", Text),
        Column("group_code", Text),
        Column("group_code_desc", Text),
        Column("complaint_code", Text),
        Column("complaint_code_desc", Text),
        Column("base_model", Text),
        Column("model_code", Text),
        Column("model_family", Text),
        Column("claim_type", Text),
        Column("sap_claim_no", Text),
        Column("claim_desc", Text),
        Column("ac_non_ac", Text),
        Column("variant", Text),
        Column("drive_type", Text),
        Column("service_type", Text),
        Column("billing_dealer", Text),
        Column("billing_dealer_name", Text),
        Column("serial_no", Text),
        Column("claim_date", Text),
        Column("failure_kms", Text),
        Column("km_hr_group", Text),
        Column("dealer_verbatim", Text),
        Column("part", Text),
        Column("vender", Text),
        Column("material_description", Text),
        Column("causal_flag", Text),
        Column("jdp_city", Text),
        Column("fisyr_qrt", Text),
        Column("engine_number", Text),
        Column("manufac_yr_mon", Text),
        Column("failure_date", Text),
        Column("mis_bucket", Text),
        Column("walk_home", Text),
        Column("dealer_code", Text),
        Column("claim_dealer_name", Text),
        Column("ro_number", Text),
        Column("no_of_incidents", Text),
        Column("new_manufacturing_quater", Text),
        Column("vendor_manuf", Text),
        Column("user_id", BigInteger, nullable=True),
        Column(
            "created_at", 
            DateTime, 
            server_default=text("CURRENT_TIMESTAMP"), 
            nullable=False
        ),
    ],
    indexes=[
        Index("idx_raw_warranty_material", "material_description"),
        Index("idx_raw_warranty_failure_date", "failure_date"),
        Index("idx_raw_warranty_user_id", "user_id"),
    ],
)


# =====================================================
# IMAGES TABLE (PartLabeler)
# =====================================================
create_dynamic_table(
    "images",
    [
        Column(
            "id",
            BigInteger,
            image_id_seq,
            primary_key=True,
            server_default=image_id_seq.next_value(),
        ),
        Column("filename", Text, nullable=False),
        Column("display_name", Text, nullable=True),
        Column("user_id", BigInteger, nullable=True),
        Column(
            "created_at", 
            DateTime, 
            server_default=text("CURRENT_TIMESTAMP"), 
            nullable=False
        ),
    ],
    indexes=[
        Index("idx_images_user_id", "user_id"),
    ],
)


# =====================================================
# LABELS TABLE (PartLabeler)
# =====================================================
create_dynamic_table(
    "labels",
    [
        Column(
            "id",
            BigInteger,
            label_id_seq,
            primary_key=True,
            server_default=label_id_seq.next_value(),
        ),
        Column(
            "image_id",
            BigInteger,
            ForeignKey("images.id", ondelete="CASCADE"),
            nullable=False,
        ),
        Column("part_name", Text, nullable=False),
        Column("description", Text, nullable=True),
        Column("part_number", Text, nullable=True),
        Column("failure_count", Integer, default=0),
        Column("report_month", Text, nullable=True),
        Column("x_coord", Float, nullable=False),
        Column("y_coord", Float, nullable=False),
        Column("user_id", BigInteger, nullable=True),
        Column(
            "created_at", 
            DateTime, 
            server_default=text("CURRENT_TIMESTAMP"), 
            nullable=False
        ),
    ],
    indexes=[
        Index("idx_labels_image_id", "image_id"),
        Index("idx_labels_user_id", "user_id"),
    ],
)



logger.info("All table definitions created successfully")
