"""
Admin API Routes
User management endpoints — only accessible by users with role='admin'.
Authorization: caller must pass their user_id as query param; backend verifies admin role.
"""

import logging
import threading
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from backend.models.schemas.auth_schemas import UpdateRoleDto, CreateUserDto

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

ALLOWED_ROLES = {"admin", "user", "part_labeler", "part_labeler_field", "part_labeler_plant"}

_auth_service = None


def get_db():
    from app.connectors.state_db_connector import StateDBConnector
    return StateDBConnector()


def get_auth_service():
    global _auth_service
    if _auth_service is None:
        from backend.services.auth.auth_service import AuthService
        _auth_service = AuthService()
    return _auth_service


def require_admin(requester_id: int):
    """
    Raises HTTPException 403 if the requesting user is not an admin.
    """
    from app.queries.auth_queries import AuthQueries
    db = get_db()
    rows = db.execute_query(AuthQueries.GET_USER_ROLE, {"user_id": requester_id})
    if not rows or rows[0][0] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/users")
async def list_users(requester_id: int = Query(..., description="user_id of the admin making the request")):
    """List all users — admin only"""
    require_admin(requester_id)
    from app.queries.auth_queries import AuthQueries
    db = get_db()
    rows = db.execute_query(AuthQueries.GET_ALL_USERS, {})
    users = [
        {
            "user_id": row[0],
            "username": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "email": row[4],
            "role": row[5],
            "created_at": str(row[6]),
        }
        for row in rows
    ]
    return JSONResponse(content={"users": users})


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    requester_id: int = Query(..., description="user_id of the admin making the request"),
):
    """Delete a user — admin only. Admin cannot delete themselves."""
    require_admin(requester_id)
    if user_id == requester_id:
        raise HTTPException(status_code=400, detail="Admin cannot delete their own account")
    from app.queries.auth_queries import AuthQueries
    db = get_db()
    db.execute_update(AuthQueries.DELETE_USER, {"user_id": user_id})
    logger.info(f"User {user_id} deleted by admin {requester_id}")
    return JSONResponse(content={"message": "User deleted successfully"})


@router.post("/users")
async def create_user(
    payload: CreateUserDto,
    requester_id: int = Query(..., description="user_id of the admin making the request"),
):
    """Create a new user with a specified role — admin only."""
    import hashlib
    from datetime import datetime, timezone
    require_admin(requester_id)
    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{payload.role}'. Allowed: {', '.join(ALLOWED_ROLES)}",
        )
    from app.queries.auth_queries import AuthQueries
    db = get_db()
    # Check username uniqueness
    existing = db.execute_query(AuthQueries.CHECK_USERNAME_EXISTS, {"username": payload.username})
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    # Check email uniqueness
    existing_email = db.execute_query(AuthQueries.CHECK_EMAIL_EXISTS, {"email": payload.email})
    if existing_email:
        raise HTTPException(status_code=409, detail="Email already registered")
    password_hash = hashlib.sha256(payload.password.encode()).hexdigest()
    rows = db.execute_query(
        AuthQueries.REGISTER_USER,
        {
            "username": payload.username,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "email": payload.email,
            "password_hash": password_hash,
            "role": payload.role,
            "created_at": datetime.now(timezone.utc),
        },
    )
    new_user_id = rows[0][0] if rows else None
    logger.info(f"User '{payload.username}' (role={payload.role}) created by admin {requester_id}")
    return JSONResponse(
        status_code=201,
        content={"message": "User created successfully", "user_id": new_user_id},
    )


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    payload: UpdateRoleDto,
    requester_id: int = Query(..., description="user_id of the admin making the request"),
):
    """Update a user's role — admin only."""
    require_admin(requester_id)
    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{payload.role}'. Allowed: {', '.join(ALLOWED_ROLES)}",
        )
    if user_id == requester_id and payload.role != "admin":
        raise HTTPException(status_code=400, detail="Admin cannot demote their own account")
    from app.queries.auth_queries import AuthQueries
    db = get_db()
    db.execute_update(AuthQueries.UPDATE_USER_ROLE, {"user_id": user_id, "role": payload.role})
    logger.info(f"User {user_id} role updated to '{payload.role}' by admin {requester_id}")
    return JSONResponse(content={"message": f"Role updated to '{payload.role}'"})


# ── QLense PDF Knowledge-Base Ingestion ──────────────────────────────────────

# Track whether an ingestion job is already running (prevents duplicate runs)
_ingestion_lock = threading.Lock()
_ingestion_running = False


def _run_pdf_ingestion():
    """
    Background worker: scans Problem_Solved PDFs, registers them in scraped_docs,
    then embeds them into OpenSearch so search_standards can retrieve solutions.
    """
    global _ingestion_running
    try:
        from app.config.config import get_settings
        from app.connectors.state_db_connector import StateDBConnector
        from dataloader.scraper.file_system_scraper import FileScraper
        from dataloader.document_embedding_processor import DocumentEmbeddingProcessor

        settings = get_settings()
        root = Path(__file__).resolve().parents[5]  # project root
        problem_solved_dir = root / "data_qlense" / "Problem_Solved"

        logger.info("=" * 60)
        logger.info("QLense PDF Ingestion — starting background job")
        logger.info(f"Source : {problem_solved_dir}")
        logger.info(f"Index  : {settings.OPENSEARCH_INDEX_NAME}")
        logger.info("=" * 60)

        db = StateDBConnector()
        scraper = FileScraper(db, settings.OPENSEARCH_INDEX_NAME)
        scrape_stats = scraper.scrape_directory(problem_solved_dir)
        db.close()

        logger.info(
            f"Scrape — scanned: {scrape_stats['scanned']}, "
            f"new: {scrape_stats['new']}, existing: {scrape_stats['existing']}, "
            f"errors: {scrape_stats['errors']}"
        )

        dep = DocumentEmbeddingProcessor()
        embed_stats = dep.run()
        dep.close()

        logger.info("=" * 60)
        logger.info("QLense PDF Ingestion — complete")
        logger.info(f"  Completed : {embed_stats['documents_completed']}/{embed_stats['documents_processed']}")
        logger.info(f"  Chunks    : {embed_stats['total_chunks_created']} created, {embed_stats['total_chunks_skipped']} skipped")
        if embed_stats["total_errors"]:
            logger.warning(f"  Errors    : {embed_stats['total_errors']}")
        logger.info("=" * 60)

    except Exception as exc:
        logger.error(f"QLense PDF ingestion failed: {exc}", exc_info=True)
    finally:
        global _ingestion_running
        with _ingestion_lock:
            _ingestion_running = False


@router.post("/qlense/ingest-pdfs")
async def ingest_qlense_pdfs(
    background_tasks: BackgroundTasks,
    requester_id: int = Query(..., description="user_id of the admin making the request"),
):
    """
    Trigger ingestion of Problem_Solved PDFs into OpenSearch for the QLense Agent.

    Scans data_qlense/Problem_Solved/, registers new PDFs in scraped_docs,
    then chunks and embeds them so search_standards can retrieve solutions in Phase 2.
    The job runs in the background — check server logs for progress.
    Admin only.
    """
    require_admin(requester_id)

    global _ingestion_running
    with _ingestion_lock:
        if _ingestion_running:
            return JSONResponse(
                status_code=409,
                content={"message": "Ingestion already running. Check server logs for progress."},
            )
        _ingestion_running = True

    background_tasks.add_task(_run_pdf_ingestion)
    logger.info(f"QLense PDF ingestion triggered by admin user_id={requester_id}")
    return JSONResponse(
        content={
            "message": "PDF ingestion started in the background. Monitor server logs for progress.",
            "source": "data_qlense/Problem_Solved/",
        }
    )
