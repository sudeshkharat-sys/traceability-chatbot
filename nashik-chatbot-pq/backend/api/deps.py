"""
Authentication / authorisation dependencies.

The role -> module matrix below MUST stay in sync with ROLE_ALLOWED in
frontend/src/services/api/authService.js.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request

from backend.services.auth.token import verify_token

logger = logging.getLogger(__name__)

# Module ids match the landing-page cards.
ROLE_ALLOWED = {
    "user":               {"part-labeler", "guideline"},
    "pfmea_advisor":      {"pfmea", "part-labeler-plant"},
    "part_labeler":       {"part-labeler", "part-labeler-plant", "guideline"},
    "part_labeler_field": {"part-labeler", "guideline"},
    "part_labeler_plant": {"part-labeler-plant", "z-stage", "guideline", "pfmea"},
    "part_labeler_ev":    {"part-labeler-ev", "z-stage", "guideline", "pfmea"},
}

PART_LABELER_MODULES = {"part-labeler", "part-labeler-plant", "part-labeler-ev"}


def _extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    # Query-param fallback for GET only: browser-driven downloads and 3D model
    # loaders cannot set headers.
    if request.method == "GET":
        return request.query_params.get("access_token")
    return None


def get_current_user(request: Request) -> dict:
    """Validate the token and load the user's current role from the DB."""
    token = _extract_token(request)
    uid = verify_token(token) if token else None
    if uid is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from app.connectors.state_db_connector import StateDBConnector
    from app.queries.auth_queries import AuthQueries

    rows = StateDBConnector().execute_query(AuthQueries.GET_USER_ROLE, {"user_id": uid})
    if not rows:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return {"user_id": uid, "role": rows[0][0]}


def require_modules(*modules: str):
    """Dependency factory: allow admin, or any role that has one of `modules`."""
    wanted = set(modules)

    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] == "admin":
            return user
        if ROLE_ALLOWED.get(user["role"], set()) & wanted:
            return user
        logger.warning("403: user=%s role=%s needs one of %s", user["user_id"], user["role"], wanted)
        raise HTTPException(status_code=403, detail="Your role does not have access to this resource")

    return _dep


def require_admin_user(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
