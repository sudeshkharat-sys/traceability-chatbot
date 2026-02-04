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
        WHERE doc_path = :doc_path AND doc_hash = :doc_hash
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
        VALUES (:index_name, :doc_name, :doc_path, :doc_hash, :status, :created_at, :updated_at)
        RETURNING id
    """

    # ==================== scraped_docs – UPDATE ====================

    UPDATE_DOCUMENT_STATUS = """
        UPDATE scraped_docs
        SET status = :status, updated_at = :updated_at
        WHERE id = :id
    """

    RESET_STATUS_BY_ID = """
        UPDATE scraped_docs
        SET status = 'incomplete', updated_at = :updated_at
        WHERE id = :id
    """

    RESET_STATUS_BY_INDEX = """
        UPDATE scraped_docs
        SET status = 'incomplete', updated_at = :updated_at
        WHERE index_name = :index_name
    """

    # ==================== chunks – SELECT ====================

    GET_CHUNK_BY_HASH = """
        SELECT chunk_id, chunk_hash FROM chunks
        WHERE chunk_hash = :chunk_hash
    """

    # ==================== chunks – INSERT / UPDATE ====================

    INSERT_CHUNK = """
        INSERT INTO chunks (doc_id, index_name, chunk_hash, chunk_text, chunk_metadata, opensearch_id, created_at, updated_at)
        VALUES (:doc_id, :index_name, :chunk_hash, :chunk_text, :chunk_metadata, :opensearch_id, :created_at, :updated_at)
        RETURNING chunk_id
    """

    UPDATE_CHUNK = """
        UPDATE chunks
        SET doc_id = :doc_id, index_name = :index_name, chunk_text = :chunk_text, chunk_metadata = :chunk_metadata,
            opensearch_id = :opensearch_id, updated_at = :updated_at
        WHERE chunk_hash = :chunk_hash
        RETURNING chunk_id
    """
