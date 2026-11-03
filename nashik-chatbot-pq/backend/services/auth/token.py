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

_DEFAULT_SECRET = "change-me-in-production"
_secret_cache = None


def _secret() -> bytes:
    """
    Use SESSION_SECRET from the environment if an operator set one. Otherwise
    generate a random secret once and keep it in the database, so every install
    gets its own unguessable key without any manual configuration.
    """
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    configured = get_settings().SESSION_SECRET
    if configured and configured != _DEFAULT_SECRET:
        _secret_cache = configured.encode()
        return _secret_cache
    try:
        import secrets
        from app.connectors.state_db_connector import StateDBConnector

        db = StateDBConnector()
        db.execute_update(
            "CREATE TABLE IF NOT EXISTS app_secrets "
            "(name VARCHAR(50) PRIMARY KEY, value VARCHAR(255) NOT NULL)"
        )
        db.execute_update(
            "INSERT INTO app_secrets (name, value) VALUES ('session_secret', :v) "
            "ON CONFLICT (name) DO NOTHING",
            {"v": secrets.token_urlsafe(48)},
        )
        rows = db.execute_query("SELECT value FROM app_secrets WHERE name = 'session_secret'")
        _secret_cache = rows[0][0].encode()
    except Exception as e:  # never fall back to the public default
        import logging, secrets
        logging.getLogger(__name__).error(
            "Could not persist session secret (%s); using a temporary random one "
            "- users will have to log in again after a restart.", e)
        _secret_cache = secrets.token_urlsafe(48).encode()
    return _secret_cache


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(body: str) -> str:
    key = _secret()
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
