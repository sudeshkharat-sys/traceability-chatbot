"""
Chat Queries
SQL queries for chat management operations.
All queries use parameterized placeholders for VAPT compliance.
"""


class ChatQueries:
    """
    SQL queries for chat management operations.
    All queries use parameterized placeholders for VAPT compliance.
    """

    # ==================== INSERT QUERIES ====================

    CREATE_CONVERSATION = """
        INSERT INTO chat_session (user_id, chat_title, agent_type, creation_ts, is_deleted)
        VALUES (:user_id, :chat_title, :agent_type, :creation_ts, :is_deleted)
        RETURNING conversation_id
    """

    SAVE_MESSAGE = """
        INSERT INTO chat_entry (conversation_id, query, response, clarification_response_needed, chat_entry_ts)
        VALUES (:conversation_id, :query, :response, :clarification_needed, :chat_entry_ts)
        RETURNING message_id
    """

    # ==================== SELECT QUERIES ====================

    GET_CONVERSATION_MESSAGES = """
        SELECT message_id, query, response, chat_entry_ts, clarification_response_needed
        FROM chat_entry
        WHERE conversation_id = :conversation_id
        ORDER BY chat_entry_ts ASC
    """

    GET_CONVERSATION_METADATA = """
        SELECT user_id, chat_title, chat_summary, creation_ts, agent_type
        FROM chat_session
        WHERE conversation_id = :conversation_id AND is_deleted = FALSE
    """

    LIST_USER_CHATS_BY_AGENT = """
        SELECT conversation_id, chat_title, creation_ts, agent_type
        FROM chat_session
        WHERE user_id = :user_id AND agent_type = :agent_type AND is_deleted = FALSE
        ORDER BY creation_ts DESC
    """

    LIST_USER_CHATS = """
        SELECT conversation_id, chat_title, creation_ts, agent_type
        FROM chat_session
        WHERE user_id = :user_id AND is_deleted = FALSE
        ORDER BY creation_ts DESC
    """

    # ==================== UPDATE QUERIES ====================

    UPDATE_CHAT_TITLE = """
        UPDATE chat_session
        SET chat_title = :title
        WHERE conversation_id = :conversation_id
    """

    SOFT_DELETE_CHAT = """
        UPDATE chat_session
        SET is_deleted = TRUE
        WHERE conversation_id = :conversation_id
    """
