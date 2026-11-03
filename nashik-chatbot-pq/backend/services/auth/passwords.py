"""
Password hashing (stdlib only): salted PBKDF2-HMAC-SHA256.

Stored format:  pbkdf2_sha256$<iterations>$<salt>$<hash>
Legacy accounts (unsalted SHA-256 hex, 64 chars) still verify, and are
re-hashed to the new format the next time the user logs in.
"""

import base64
import hashlib
import hmac
import os

ITERATIONS = 310_000
PREFIX = "pbkdf2_sha256"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def hash_password(password: str) -> str:
    """Store a password. Uses the legacy format until PASSWORD_HASH_UPGRADE is on."""
    from app.config.config import get_settings
    if not get_settings().PASSWORD_HASH_UPGRADE:
        return hashlib.sha256(password.encode()).hexdigest()
    return hash_password_pbkdf2(password)


def hash_password_pbkdf2(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"{PREFIX}${ITERATIONS}${_b64(salt)}${_b64(dk)}"


def _is_legacy(stored: str) -> bool:
    return len(stored) == 64 and all(c in "0123456789abcdef" for c in stored.lower())


def verify_password(password: str, stored: str):
    """Return (is_valid, needs_upgrade)."""
    if not stored:
        return False, False
    if _is_legacy(stored):
        ok = hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), stored.lower())
        return ok, ok
    try:
        prefix, iters, salt, expected = stored.split("$")
        if prefix != PREFIX:
            return False, False
        pad = lambda s: s + "=" * (-len(s) % 4)
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.urlsafe_b64decode(pad(salt)), int(iters)
        )
        return hmac.compare_digest(_b64(dk), expected), False
    except Exception:
        return False, False
