"""
Simple in-memory brute-force protection for login / password reset.
Locks a username out for WINDOW seconds after MAX_FAILURES wrong attempts.
(Per-process memory: resets on restart, which is acceptable for this purpose.)
"""

import threading
import time
from collections import defaultdict

MAX_FAILURES = 5
WINDOW = 15 * 60

_lock = threading.Lock()
_failures = defaultdict(list)


def _recent(key: str) -> list:
    cutoff = time.time() - WINDOW
    _failures[key] = [t for t in _failures[key] if t > cutoff]
    return _failures[key]


def seconds_locked(username: str) -> int:
    """0 if allowed, otherwise seconds remaining on the lockout."""
    key = username.strip().lower()
    with _lock:
        recent = _recent(key)
        if len(recent) >= MAX_FAILURES:
            return int(recent[0] + WINDOW - time.time()) + 1
    return 0


def record_failure(username: str) -> None:
    with _lock:
        _recent(username.strip().lower()).append(time.time())


def clear(username: str) -> None:
    with _lock:
        _failures.pop(username.strip().lower(), None)
