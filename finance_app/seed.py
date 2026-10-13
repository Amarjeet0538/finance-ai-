"""Seed script for mock finance app database.

Inserts baseline admin and operator accounts.
Idempotent: skips existing records unless --reset is passed.
"""

import argparse
import hashlib
import sys
from sqlalchemy.orm import Session

from finance_app.database import SessionLocal, init_db, reset_db
from finance_app.models import User


def hash_password(password: str) -> str:
    """Generate deterministic SHA-256 hash for password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check plain password against hash."""
    return hash_password(plain_password) == hashed_password


def seed_database(reset: bool = False) -> None:
    """Seed the database with default users."""
    if reset:
        print("Resetting database schema...")
        reset_db()
    else:
        init_db()

    session: Session = SessionLocal()
    try:
        # Check / create admin user
        admin = session.query(User).filter_by(username="admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin"),
                is_admin=True,
            )
            session.add(admin)
            print("Created user: admin")

        # Check / create operator user
        operator = session.query(User).filter_by(username="operator").first()
        if not operator:
            operator = User(
                username="operator",
                password_hash=hash_password("password"),
                is_admin=False,
            )
            session.add(operator)
            print("Created user: operator")

        session.commit()
        user_count = session.query(User).count()
        print(f"Seed completed. Total users in database: {user_count}")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed mock finance app database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe all tables and reseed from scratch.",
    )
    args = parser.parse_args()
    seed_database(reset=args.reset)
