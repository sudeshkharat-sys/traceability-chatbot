"""
Auth Queries
SQL queries for user authentication and management.
All queries use parameterized placeholders for security.
"""


class AuthQueries:
    """
    SQL queries for user authentication and management.
    """

    # ==================== SELECT QUERIES ====================

    CHECK_USERNAME_EXISTS = """
        SELECT user_id FROM users WHERE username = :username
    """

    CHECK_EMAIL_EXISTS = """
        SELECT user_id FROM users WHERE email = :email
    """

    AUTHENTICATE_USER = """
        SELECT user_id, username, first_name, last_name 
        FROM users 
        WHERE username = :username AND password_hash = :password_hash
    """

    # ==================== INSERT QUERIES ====================

    REGISTER_USER = """
        INSERT INTO users (username, first_name, last_name, email, password_hash, created_at)
        VALUES (:username, :first_name, :last_name, :email, :password_hash, :created_at)
        RETURNING user_id
    """
