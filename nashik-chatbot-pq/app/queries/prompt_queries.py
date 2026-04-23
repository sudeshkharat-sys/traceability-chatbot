"""
Prompt Queries
SQL queries for prompt management operations.
All queries use parameterized placeholders for VAPT compliance.
"""


class PromptQueries:
    """
    SQL queries for prompt management operations.
    All queries use parameterized placeholders for VAPT compliance.
    """

    # ==================== SELECT QUERIES ====================

    GET_PROMPT_BY_KEY = """
        SELECT prompt_content 
        FROM system_prompts 
        WHERE prompt_key = :key
    """

    GET_ALL_PROMPTS = """
        SELECT prompt_key, prompt_name, prompt_content, updated_at
        FROM system_prompts 
        ORDER BY prompt_key
    """

    GET_PROMPT_ID_BY_KEY = """
        SELECT prompt_id FROM system_prompts WHERE prompt_key = :key
    """

    CHECK_PROMPT_EXISTS = """
        SELECT 1 FROM system_prompts WHERE prompt_key = :key
    """

    # ==================== INSERT QUERIES ====================

    INSERT_PROMPT = """
        INSERT INTO system_prompts 
        (prompt_key, prompt_name, prompt_content, created_at, updated_at)
        VALUES (:key, :name, :content, NOW(), NOW())
    """

    # ==================== UPDATE QUERIES ====================

    UPDATE_PROMPT = """
        UPDATE system_prompts 
        SET prompt_name = :name,
            prompt_content = :content,
            updated_at = NOW()
        WHERE prompt_key = :key
    """

    UPDATE_PROMPT_CONTENT = """
        UPDATE system_prompts 
        SET prompt_content = :content,
            updated_at = NOW()
        WHERE prompt_key = :key
    """
