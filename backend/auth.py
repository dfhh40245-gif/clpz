"""Local authentication for CLPZ.

Provides user accounts with password hashing and session tokens.
All data stored in SQLite via database.py.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import time

import database as db

# RFC-compliant-ish email pattern: rejects HTML, special chars, enforces max length
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
_MAX_EMAIL_LEN = 254  # RFC 5321


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-SHA256. Returns (hash, salt)."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return dk.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against stored hash."""
    computed, _ = _hash_password(password, salt)
    return secrets.compare_digest(computed, stored_hash)


def create_user(email: str, password: str, display_name: str = "") -> dict:
    """Create a new user account. Returns user dict or raises ValueError."""
    email = email.strip().lower()
    if not email or len(email) > _MAX_EMAIL_LEN or not _EMAIL_RE.match(email):
        raise ValueError("Invalid email address.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    if db.user_exists(email):
        raise ValueError("An account with this email already exists.")

    pwd_hash, salt = _hash_password(password)
    user_id = secrets.token_hex(8)
    name = display_name or email.split("@")[0]

    db.create_user(user_id, email, pwd_hash, salt, display_name=name)
    return {"id": user_id, "email": email, "display_name": name}


def authenticate_user(email: str, password: str) -> dict | None:
    """Authenticate and return user dict, or None if invalid."""
    email = email.strip().lower()
    pw_data = db.get_user_password(email)
    if not pw_data:
        return None
    if not _verify_password(password, pw_data["password_hash"], pw_data["password_salt"]):
        return None
    user = db.get_user_by_email(email)
    return user


def create_session(user_id: str) -> str:
    """Create a session token. Returns the token string."""
    return db.create_session(user_id)


def validate_session(token: str) -> str | None:
    """Validate a session token. Returns user_id or None."""
    return db.validate_session(token)


def destroy_session(token: str) -> None:
    """Destroy a session."""
    db.destroy_session(token)


def get_user_by_id(user_id: str) -> dict | None:
    """Get user by ID (without password data)."""
    return db.get_user_by_id(user_id)


def get_user_by_email(email: str) -> dict | None:
    """Get user by email (without password data)."""
    return db.get_user_by_email(email.strip().lower())


def set_password(user_id: str, new_password: str) -> None:
    """Set a new password for a user by ID."""
    if len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    pwd_hash, salt = _hash_password(new_password)
    db.set_password(user_id, pwd_hash, salt)


def destroy_all_user_sessions(user_id: str) -> None:
    """Destroy all sessions for a user (force re-login)."""
    db.destroy_all_user_sessions(user_id)


def reset_password(email: str, new_password: str) -> bool:
    """Reset a user's password. Returns True if user exists."""
    email = email.strip().lower()
    user = db.get_user_by_email(email)
    if not user:
        return False
    if len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    set_password(user["id"], new_password)
    return True


# -- Email verification -------------------------------------------

def generate_verification_code(user_id: str, purpose: str = "signup") -> str:
    """Generate a 6-digit verification code for a user. Returns the code."""
    code = f"{secrets.randbelow(900000) + 100000}"
    db.save_verification_code(user_id, code, purpose, time.time() + 900)  # 15 minutes
    return code


def verify_code(user_id: str, code: str, purpose: str = "signup") -> bool:
    """Verify a 6-digit code. Returns True if valid and deletes it."""
    return db.verify_code(user_id, code, purpose)


def mark_email_verified(user_id: str) -> None:
    """Mark a user's email as verified."""
    db.mark_email_verified(user_id)


def is_email_verified(user_id: str) -> bool:
    """Check if a user's email is verified."""
    return db.is_email_verified(user_id)
