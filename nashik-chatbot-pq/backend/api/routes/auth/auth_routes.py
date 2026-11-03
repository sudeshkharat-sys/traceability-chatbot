"""
Authentication API Routes
Handles signup, login, and logout endpoints
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import hashlib
from backend.services.auth.token import create_token
from backend.services.auth.passwords import hash_password, verify_password
from backend.services.auth import rate_limit
from backend.models.schemas.auth_schemas import SignupDto, LoginDto, ResetPasswordDto

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

_auth_service = None


def get_auth_service():
    """Lazy-load the auth service"""
    global _auth_service
    if _auth_service is None:
        from backend.services.auth.auth_service import AuthService
        _auth_service = AuthService()
    return _auth_service


@router.post("/signup")
async def signup(payload: SignupDto):
    """Register a new user"""
    try:
        result = get_auth_service().signup(
            payload.username, payload.first_name, payload.last_name,
            payload.email, payload.password
        )
        return JSONResponse(
            content={
                "user_id": result["user_id"],
                "username": result["username"],
                "first_name": result["first_name"],
                "last_name": result["last_name"],
                "role": result["role"],
                "message": "Signup successful",
            },
            status_code=201,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Signup error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Signup failed")


@router.post("/login")
async def login(payload: LoginDto):
    """Authenticate a user"""
    wait = rate_limit.seconds_locked(payload.username)
    if wait:
        raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {wait // 60 + 1} minute(s).")
    try:
        result = get_auth_service().login(payload.username, payload.password)
        rate_limit.clear(payload.username)
        return JSONResponse(
            content={
                "user_id": result["user_id"],
                "username": result["username"],
                "first_name": result["first_name"],
                "last_name": result["last_name"],
                "role": result["role"],
                "token": create_token(result["user_id"]),
                "message": "Login successful",
            }
        )
    except ValueError as e:
        rate_limit.record_failure(payload.username)
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordDto):
    """Reset a user's password by username"""
    from app.queries.auth_queries import AuthQueries
    from app.connectors.state_db_connector import StateDBConnector
    if not payload.new_password:
        raise HTTPException(status_code=400, detail="New password cannot be empty")
    wait = rate_limit.seconds_locked(payload.username)
    if wait:
        raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {wait // 60 + 1} minute(s).")
    db = StateDBConnector()
    existing = db.execute_query(AuthQueries.CHECK_USERNAME_EXISTS, {"username": payload.username})
    if not existing:
        raise HTTPException(status_code=404, detail="Username not found")
    # Verify current password
    rows = db.execute_query(AuthQueries.GET_PASSWORD_HASH, {"username": payload.username})
    stored_hash = rows[0][0] if rows else None
    valid, _ = verify_password(payload.current_password, stored_hash)
    if not valid:
        rate_limit.record_failure(payload.username)
        raise HTTPException(status_code=401, detail="Current password is incorrect. Please contact your admin.")
    rate_limit.clear(payload.username)
    new_hash = hash_password(payload.new_password)
    db.execute_update(AuthQueries.RESET_PASSWORD, {"username": payload.username, "password_hash": new_hash})
    logger.info(f"Password reset for user '{payload.username}'")
    return JSONResponse(content={"message": "Password reset successful"})


@router.post("/logout")
async def logout():
    """
    Logout endpoint.
    Session is managed on the frontend via sessionStorage.
    This endpoint confirms logout on the server side.
    """
    return JSONResponse(content={"message": "Logout successful"})
