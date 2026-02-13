"""
Authentication Service
Handles user signup, login, and session management
"""

import hashlib
import logging

from app.connectors.state_db_connector import StateDBConnector

logger = logging.getLogger(__name__)


class AuthService:
    """Manages user authentication against PostgreSQL"""

    def __init__(self):
        self.db = StateDBConnector()

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def signup(self, username: str, email: str, password: str) -> dict:
        """
        Register a new user.

        Returns:
            dict with user_id and username on success

        Raises:
            ValueError if username or email already exists
        """
        # Check if username already exists
        rows = self.db.execute_query(
            "SELECT user_id FROM users WHERE username = :username",
            {"username": username},
        )
        if rows:
            raise ValueError("Username already exists")

        # Check if email already exists
        rows = self.db.execute_query(
            "SELECT user_id FROM users WHERE email = :email",
            {"email": email},
        )
        if rows:
            raise ValueError("Email already exists")

        password_hash = self._hash_password(password)

        user_id = self.db.execute_insert(
            "INSERT INTO users (username, email, password_hash) "
            "VALUES (:username, :email, :password_hash) RETURNING user_id",
            {"username": username, "email": email, "password_hash": password_hash},
        )

        logger.info(f"New user registered: {username} (id={user_id})")
        return {"user_id": user_id, "username": username}

    def login(self, username: str, password: str) -> dict:
        """
        Authenticate a user.

        Returns:
            dict with user_id and username on success

        Raises:
            ValueError if credentials are invalid
        """
        password_hash = self._hash_password(password)

        rows = self.db.execute_query(
            "SELECT user_id, username FROM users "
            "WHERE username = :username AND password_hash = :password_hash",
            {"username": username, "password_hash": password_hash},
        )

        if not rows:
            raise ValueError("Invalid username or password")

        row = rows[0]
        logger.info(f"User logged in: {row[1]} (id={row[0]})")
        return {"user_id": row[0], "username": row[1]}
