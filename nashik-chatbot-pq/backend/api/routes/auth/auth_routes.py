"""
Authentication API Routes
Handles signup, login, and logout endpoints
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from backend.models.schemas.auth_schemas import SignupDto, LoginDto

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
    try:
        result = get_auth_service().login(payload.username, payload.password)
        return JSONResponse(
            content={
                "user_id": result["user_id"],
                "username": result["username"],
                "first_name": result["first_name"],
                "last_name": result["last_name"],
                "message": "Login successful",
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/logout")
async def logout():
    """
    Logout endpoint.
    Session is managed on the frontend via sessionStorage.
    This endpoint confirms logout on the server side.
    """
    return JSONResponse(content={"message": "Logout successful"})
