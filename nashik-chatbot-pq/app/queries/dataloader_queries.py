"""
Dataloader Queries
SQL queries for the document scraping and embedding pipeline.
"""


class DataloaderQueries:
    """
    SQL queries for the scrape → embed document processing pipeline.
    Covers the scraped_docs and chunks tables.
    """

    # ==================== scraped_docs – SELECT ====================

    GET_INCOMPLETE_DOCUMENTS = """
        SELECT id, index_name, doc_name, doc_path, doc_hash
        FROM scraped_docs
        WHERE status = 'incomplete'
        ORDER BY created_at ASC
    """

    CHECK_DOCUMENT_SCRAPED = """
        SELECT COUNT(*) as count FROM scraped_docs
        WHERE doc_path = %s AND doc_hash = %s
    """

    LIST_DOCUMENTS_BASE = """
        SELECT id, index_name, doc_name, status, created_at, updated_at
        FROM scraped_docs
    """

    STATUS_COUNTS = """
        SELECT status, COUNT(*) as count
        FROM scraped_docs
        GROUP BY status
    """

    # ==================== scraped_docs – INSERT ====================

    INSERT_SCRAPED_DOC = """
        INSERT INTO scraped_docs (index_name, doc_name, doc_path, doc_hash, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    # ==================== scraped_docs – UPDATE ====================

    UPDATE_DOCUMENT_STATUS = """
        UPDATE scraped_docs
        SET status = %s, updated_at = %s
        WHERE id = %s
    """

    RESET_STATUS_BY_ID = """
        UPDATE scraped_docs
        SET status = 'incomplete', updated_at = %s
        WHERE id = %s
    """

    RESET_STATUS_BY_INDEX = """
        UPDATE scraped_docs
        SET status = 'incomplete', updated_at = %s
        WHERE index_name = %s
    """

    # ==================== chunks – SELECT ====================

    GET_CHUNK_BY_HASH = """
        SELECT chunk_id, chunk_hash FROM chunks
        WHERE chunk_hash = %s
    """

    # ==================== chunks – INSERT / UPDATE ====================

    INSERT_CHUNK = """
        INSERT INTO chunks (doc_id, index_name, chunk_hash, chunk_text, chunk_metadata, opensearch_id, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING chunk_id
    """

    UPDATE_CHUNK = """
        UPDATE chunks
        SET doc_id = %s, index_name = %s, chunk_text = %s, chunk_metadata = %s,
            opensearch_id = %s, updated_at = %s
        WHERE chunk_hash = %s
        RETURNING chunk_id
    """
