"""
VAPT Test Accounts
==================
Creates one login per role for the VAPT (security testing) team, with random
strong passwords, and prints them once. Remove them after the audit.

Usage (run from the nashik-chatbot-pq folder, backend environment active):

    python scripts/create_vapt_users.py                    # create the accounts
    python scripts/create_vapt_users.py --reset-passwords  # new passwords for existing vapt_* accounts
    python scripts/create_vapt_users.py --delete           # remove all vapt_* accounts after the audit
    python scripts/create_vapt_users.py --out creds.csv    # also save the credentials to a file

Passwords are shown only at creation/reset time and are not stored anywhere
in readable form. Share them over a secure channel (not e-mail / chat).
"""

import argparse
import csv
import datetime
import os
import secrets
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.connectors.state_db_connector import StateDBConnector
from backend.services.auth.passwords import hash_password

# (username, role, description)
ACCOUNTS = [
    ("vapt_admin",         "admin",              "Full access + Admin Panel"),
    ("vapt_user",          "user",               "Default signup role (Part Sense Field, Guidelines)"),
    ("vapt_part_labeler",  "part_labeler",       "Part Sense Field + Plant, Guidelines"),
    ("vapt_pl_field",      "part_labeler_field", "Part Sense Field, Guidelines"),
    ("vapt_pl_plant",      "part_labeler_plant", "Part Sense Plant, Z-Stage, Guidelines, PFMEA"),
    ("vapt_pl_ev",         "part_labeler_ev",    "Part Sense EV, Z-Stage, Guidelines"),
    ("vapt_pfmea",         "pfmea_advisor",      "PFMEA, Part Sense Plant"),
]


def new_password(length: int = 16) -> str:
    """Random password that always contains lower, upper, digit and symbol."""
    sets = [string.ascii_lowercase, string.ascii_uppercase, string.digits, "!@#$%^*-_=+"]
    chars = [secrets.choice(s) for s in sets]
    pool = "".join(sets)
    chars += [secrets.choice(pool) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def main():
    ap = argparse.ArgumentParser(description="Create / reset / delete VAPT test accounts",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--reset-passwords", action="store_true", help="give existing vapt_* accounts new passwords")
    ap.add_argument("--delete", action="store_true", help="delete all vapt_* accounts")
    ap.add_argument("--out", default=None, help="also write credentials to this CSV file")
    args = ap.parse_args()

    db = StateDBConnector()
    names = [a[0] for a in ACCOUNTS]

    if args.delete:
        n = 0
        for u in names:
            n += db.execute_update("DELETE FROM users WHERE username = :u", {"u": u})
        print(f"Deleted {n} VAPT account(s).")
        return

    rows = []
    for username, role, desc in ACCOUNTS:
        exists = db.execute_query("SELECT user_id FROM users WHERE username = :u", {"u": username})
        if exists and not args.reset_passwords:
            print(f"[SKIPPED] {username} already exists (use --reset-passwords for a new password)")
            continue
        pw = new_password()
        if exists:
            db.execute_update(
                "UPDATE users SET password_hash = :h, role = :r WHERE username = :u",
                {"h": hash_password(pw), "r": role, "u": username},
            )
            status = "RESET"
        else:
            db.execute_insert(
                "INSERT INTO users (username, first_name, last_name, email, password_hash, role, created_at) "
                "VALUES (:u, 'VAPT', :ln, :e, :h, :r, :t) RETURNING user_id",
                {"u": username, "ln": role, "e": f"{username}@vapt.local",
                 "h": hash_password(pw), "r": role, "t": datetime.datetime.utcnow()},
            )
            status = "CREATED"
        rows.append((username, pw, role, desc))
        print(f"[{status}] {username}  role={role}")

    if rows:
        print("\n" + "=" * 78)
        print(f"{'USERNAME':<20}{'PASSWORD':<20}{'ROLE':<22}ACCESS")
        print("-" * 78)
        for u, p, r, d in rows:
            print(f"{u:<20}{p:<20}{r:<22}{d}")
        print("=" * 78)
        print("Share these over a secure channel. They are not shown again.")
        if args.out:
            with open(args.out, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["username", "password", "role", "access"])
                w.writerows(rows)
            print(f"Saved to {args.out} - delete this file after sharing.")


if __name__ == "__main__":
    main()
