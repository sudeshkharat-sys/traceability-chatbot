"""
Admin User Seed Script
======================
Creates admin accounts directly in the database.
Public signup always creates the 'user' role — use this script to
bootstrap the first admin (or any additional admins).

Usage:
    cd nashik-chatbot-pq

    # Create a single admin (interactive password prompt)
    python scripts/create_users.py --username admin --email admin@company.com

    # Pass all values as flags (non-interactive)
    python scripts/create_users.py \\
        --username admin \\
        --first-name Admin \\
        --last-name User \\
        --email admin@company.com \\
        --password "Admin@1234"

    # Create a different role (admin | user | part_labeler)
    python scripts/create_users.py \\
        --username labeler1 \\
        --email labeler1@company.com \\
        --role part_labeler \\
        --password "Labeler@1"
"""

import sys
import os
import argparse
import hashlib
import getpass
import datetime

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.connectors.state_db_connector import StateDBConnector

ALLOWED_ROLES = {"admin", "user", "part_labeler"}

INSERT_SQL = """
    INSERT INTO users (username, first_name, last_name, email, password_hash, role, created_at)
    VALUES (:username, :first_name, :last_name, :email, :password_hash, :role, :created_at)
    ON CONFLICT (username) DO NOTHING
    RETURNING user_id
"""

CHECK_EMAIL_SQL = "SELECT user_id FROM users WHERE email = :email"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(
        description="Create an admin (or other role) user directly in the database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--username",   required=True,  help="Login username")
    parser.add_argument("--email",      required=True,  help="User e-mail address")
    parser.add_argument("--first-name", default="Admin", dest="first_name", help="First name (default: Admin)")
    parser.add_argument("--last-name",  default="User",  dest="last_name",  help="Last name  (default: User)")
    parser.add_argument("--password",   default=None,   help="Password (omit to be prompted securely)")
    parser.add_argument(
        "--role",
        default="admin",
        choices=sorted(ALLOWED_ROLES),
        help="Role to assign — admin | user | part_labeler  (default: admin)",
    )
    args = parser.parse_args()

    # Prompt for password if not supplied on the command line
    password = args.password
    if not password:
        password = getpass.getpass(f"Password for '{args.username}': ")
        confirm  = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Error: passwords do not match.", file=sys.stderr)
            sys.exit(1)

    if not password:
        print("Error: password cannot be empty.", file=sys.stderr)
        sys.exit(1)

    db = StateDBConnector()

    # Check email uniqueness
    if db.execute_query(CHECK_EMAIL_SQL, {"email": args.email}):
        print(f"Error: e-mail '{args.email}' is already registered.", file=sys.stderr)
        sys.exit(1)

    params = {
        "username":      args.username,
        "first_name":    args.first_name,
        "last_name":     args.last_name,
        "email":         args.email,
        "password_hash": hash_password(password),
        "role":          args.role,
        "created_at":    datetime.datetime.utcnow(),
    }

    result = db.execute_insert(INSERT_SQL, params)
    if result:
        print(f"[CREATED] '{args.username}'  role={args.role}  id={result}")
    else:
        print(f"[SKIPPED] Username '{args.username}' already exists in the database.")


if __name__ == "__main__":
    main()
