"""
Authentication Service
Handles user signup, login, and session management
"""

import logging
import datetime

from app.connectors.state_db_connector import StateDBConnector
from app.queries import AuthQueries
from backend.services.auth.passwords import hash_password, verify_password

logger = logging.getLogger(__name__)


class AuthService:
    """Manages user authentication against PostgreSQL"""

    def __init__(self):
        self.db = StateDBConnector()

    @staticmethod
    def _hash_password(password: str) -> str:
        return hash_password(password)

    def signup(self, username: str, first_name: str, last_name: str, email: str, password: str) -> dict:
        """
        Register a new user.

        Returns:
            dict with user_id, username, first_name, last_name on success

        Raises:
            ValueError if username or email already exists
        """
        # Check if username already exists
        rows = self.db.execute_query(
            AuthQueries.CHECK_USERNAME_EXISTS,
            {"username": username},
        )
        if rows:
            raise ValueError("Username already exists")

        # Check if email already exists
        rows = self.db.execute_query(
            AuthQueries.CHECK_EMAIL_EXISTS,
            {"email": email},
        )
        if rows:
            raise ValueError("Email already exists")

        password_hash = self._hash_password(password)

        user_id = self.db.execute_insert(
            AuthQueries.REGISTER_USER,
            {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "password_hash": password_hash,
                "role": "user",
                "created_at": datetime.datetime.utcnow(),
            },
        )

        logger.info(f"New user registered (id={user_id})")
        return {"user_id": user_id, "username": username, "first_name": first_name, "last_name": last_name, "role": "user"}

    def login(self, username: str, password: str) -> dict:
        """
        Authenticate a user.

        Returns:
            dict with user_id and username on success

        Raises:
            ValueError if credentials are invalid
        """
        rows = self.db.execute_query(AuthQueries.GET_USER_FOR_LOGIN, {"username": username})
        ok, needs_upgrade = verify_password(password, rows[0][5]) if rows else (False, False)
        if not ok:
            raise ValueError("Invalid username or password")

        from app.config.config import get_settings
        if needs_upgrade and get_settings().PASSWORD_HASH_UPGRADE:
            # Legacy unsalted SHA-256 hash: transparently move to salted PBKDF2.
            self.db.execute_update(
                AuthQueries.RESET_PASSWORD,
                {"username": username, "password_hash": hash_password(password)},
            )

        row = rows[0]
        logger.info(f"User logged in (id={row[0]}) role={row[4]}")
        return {"user_id": row[0], "username": row[1], "first_name": row[2], "last_name": row[3], "role": row[4]}
