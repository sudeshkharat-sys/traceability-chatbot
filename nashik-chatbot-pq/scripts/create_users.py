"""
User Seed Script
================
Creates admin and part_labeler users directly in the database.
Public signup always creates 'user' role — use this script for
admin and part_labeler accounts.

Usage:
    cd nashik-chatbot-pq
    python scripts/create_users.py

Roles:
    admin        — all features + admin user-management panel
    user         — all features (what public signup gives)
    part_labeler — only PartLabeler field + plant

EDIT THE LISTS BELOW BEFORE RUNNING.
"""

import sys
import os
import hashlib
import datetime

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.connectors.state_db_connector import StateDBConnector

# ─────────────────────────────────────────────────────────────
# 1.  ADMIN USERS  (created via script — never via public signup)
# ─────────────────────────────────────────────────────────────
ADMIN_USERS = [
    {
        "username":   "admin",
        "first_name": "Admin",
        "last_name":  "User",
        "email":      "admin@company.com",
        "password":   "Admin@1234",      # ← change before running
        "role":       "admin",
    },
]

# ─────────────────────────────────────────────────────────────
# 2.  PART-LABELER USERS  (17 restricted users)
#     Only access: PartLabeler Field + Plant
# ─────────────────────────────────────────────────────────────
PART_LABELER_USERS = [
    {"username": "pl_user01", "first_name": "User",  "last_name": "01", "email": "pluser01@company.com", "password": "PLUser01@"},
    {"username": "pl_user02", "first_name": "User",  "last_name": "02", "email": "pluser02@company.com", "password": "PLUser02@"},
    {"username": "pl_user03", "first_name": "User",  "last_name": "03", "email": "pluser03@company.com", "password": "PLUser03@"},
    {"username": "pl_user04", "first_name": "User",  "last_name": "04", "email": "pluser04@company.com", "password": "PLUser04@"},
    {"username": "pl_user05", "first_name": "User",  "last_name": "05", "email": "pluser05@company.com", "password": "PLUser05@"},
    {"username": "pl_user06", "first_name": "User",  "last_name": "06", "email": "pluser06@company.com", "password": "PLUser06@"},
    {"username": "pl_user07", "first_name": "User",  "last_name": "07", "email": "pluser07@company.com", "password": "PLUser07@"},
    {"username": "pl_user08", "first_name": "User",  "last_name": "08", "email": "pluser08@company.com", "password": "PLUser08@"},
    {"username": "pl_user09", "first_name": "User",  "last_name": "09", "email": "pluser09@company.com", "password": "PLUser09@"},
    {"username": "pl_user10", "first_name": "User",  "last_name": "10", "email": "pluser10@company.com", "password": "PLUser10@"},
    {"username": "pl_user11", "first_name": "User",  "last_name": "11", "email": "pluser11@company.com", "password": "PLUser11@"},
    {"username": "pl_user12", "first_name": "User",  "last_name": "12", "email": "pluser12@company.com", "password": "PLUser12@"},
    {"username": "pl_user13", "first_name": "User",  "last_name": "13", "email": "pluser13@company.com", "password": "PLUser13@"},
    {"username": "pl_user14", "first_name": "User",  "last_name": "14", "email": "pluser14@company.com", "password": "PLUser14@"},
    {"username": "pl_user15", "first_name": "User",  "last_name": "15", "email": "pluser15@company.com", "password": "PLUser15@"},
    {"username": "pl_user16", "first_name": "User",  "last_name": "16", "email": "pluser16@company.com", "password": "PLUser16@"},
    {"username": "pl_user17", "first_name": "User",  "last_name": "17", "email": "pluser17@company.com", "password": "PLUser17@"},
]


# ─────────────────────────────────────────────────────────────
# Internals — do not edit below this line
# ─────────────────────────────────────────────────────────────

INSERT_SQL = """
    INSERT INTO users (username, first_name, last_name, email, password_hash, role, created_at)
    VALUES (:username, :first_name, :last_name, :email, :password_hash, :role, :created_at)
    ON CONFLICT (username) DO NOTHING
    RETURNING user_id
"""

CHECK_EMAIL_SQL = "SELECT user_id FROM users WHERE email = :email"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_users(users: list, role: str, db: StateDBConnector):
    created = 0
    skipped = 0
    for u in users:
        # Skip if email already exists
        existing = db.execute_query(CHECK_EMAIL_SQL, {"email": u["email"]})
        if existing:
            print(f"  [SKIP]    {u['username']} — email already in use")
            skipped += 1
            continue

        params = {
            "username":      u["username"],
            "first_name":    u["first_name"],
            "last_name":     u["last_name"],
            "email":         u["email"],
            "password_hash": hash_password(u["password"]),
            "role":          u.get("role", role),
            "created_at":    datetime.datetime.utcnow(),
        }
        result = db.execute_insert(INSERT_SQL, params)
        if result:
            print(f"  [CREATED] {u['username']} (id={result}) role={params['role']}")
            created += 1
        else:
            print(f"  [SKIP]    {u['username']} — username already exists")
            skipped += 1
    return created, skipped


def main():
    print("=" * 55)
    print("  User Seed Script")
    print("=" * 55)

    db = StateDBConnector()

    print("\n▶ Creating admin users...")
    c, s = create_users(ADMIN_USERS, "admin", db)
    print(f"  → {c} created, {s} skipped\n")

    print("▶ Creating part_labeler users (17)...")
    c, s = create_users(PART_LABELER_USERS, "part_labeler", db)
    print(f"  → {c} created, {s} skipped\n")

    print("Done. Edit usernames/passwords in this file before distributing.")


if __name__ == "__main__":
    main()
