"""
Signed access tokens (stdlib only, HMAC-SHA256).

Token format:  base64url(json payload) + "." + base64url(signature)
Payload:       {"uid": <int>, "exp": <unix seconds>}

The role is deliberately NOT stored in the token: it is re-read from the
database on every request, so an admin changing a role (or deleting a user)
takes effect immediately.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from app.config.config import get_settings

TOKEN_TTL_SECONDS = 8 * 60 * 60  # 8 hours

if get_settings().SESSION_SECRET == "change-me-in-production":
    import logging
    logging.getLogger(__name__).warning(
        "SESSION_SECRET is the default value - set a long random value in .env; "
        "tokens can be forged otherwise."
    )


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(body: str) -> str:
    key = get_settings().SESSION_SECRET.encode()
    return _b64(hmac.new(key, body.encode(), hashlib.sha256).digest())


def create_token(user_id: int, ttl: int = TOKEN_TTL_SECONDS) -> str:
    body = _b64(json.dumps({"uid": int(user_id), "exp": int(time.time()) + ttl}).encode())
    return f"{body}.{_sign(body)}"


def verify_token(token: str) -> Optional[int]:
    """Return the user_id if the token is valid and unexpired, else None."""
    try:
        body, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(body)):
            return None
        payload = json.loads(_unb64(body))
        if payload["exp"] < time.time():
            return None
        return int(payload["uid"])
    except Exception:
        return None
