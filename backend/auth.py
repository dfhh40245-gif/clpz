"""Local authentication for CLPZ desktop app.

Provides user accounts with password hashing and session tokens.
No cloud dependency — all data stored locally.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

import config

_USERS_FILE = config.DATA_DIR / "users.json"
_lock = threading.Lock()

# In-memory session store: token -> {user_id, created_at}
_sessions: dict[str, dict] = {}
_MAX_SESSION_AGE = 86400 * 7  # 7 days


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


def _load_users() -> dict:
    """Load users from disk."""
    if not _USERS_FILE.exists():
        return {}
    try:
        return json.loads(_USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_users(users: dict) -> None:
    """Save users to disk."""
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def create_user(email: str, password: str, display_name: str = "") -> dict:
    """Create a new user account. Returns user dict or raises ValueError."""
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Invalid email address.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    with _lock:
        users = _load_users()
        if email in users:
            raise ValueError("An account with this email already exists.")

        pwd_hash, salt = _hash_password(password)
        user_id = secrets.token_hex(8)

        users[email] = {
            "id": user_id,
            "email": email,
            "display_name": display_name or email.split("@")[0],
            "password_hash": pwd_hash,
            "password_salt": salt,
            "created_at": time.time(),
            "uses_remaining": 10,  # Free tier: 10 uses
            "plan": "free",
        }
        _save_users(users)

    return {"id": user_id, "email": email, "display_name": users[email]["display_name"]}


def authenticate_user(email: str, password: str) -> dict | None:
    """Authenticate and return user dict, or None if invalid."""
    email = email.strip().lower()
    with _lock:
        users = _load_users()
        user = users.get(email)
        if not user:
            return None
        if not _verify_password(password, user["password_hash"], user["password_salt"]):
            return None
    return {"id": user["id"], "email": user["email"], "display_name": user.get("display_name", "")}


def create_session(user_id: str) -> str:
    """Create a session token. Returns the token string."""
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = {
            "user_id": user_id,
            "created_at": time.time(),
        }
    return token


def validate_session(token: str) -> str | None:
    """Validate a session token. Returns user_id or None."""
    if not token:
        return None
    session = _sessions.get(token)
    if not session:
        return None
    if time.time() - session["created_at"] > _MAX_SESSION_AGE:
        _sessions.pop(token, None)
        return None
    return session["user_id"]


def destroy_session(token: str) -> None:
    """Destroy a session."""
    _sessions.pop(token, None)


def get_user_by_id(user_id: str) -> dict | None:
    """Get user by ID (without password data)."""
    with _lock:
        users = _load_users()
        for user in users.values():
            if user["id"] == user_id:
                return {
                    "id": user["id"],
                    "email": user["email"],
                    "display_name": user.get("display_name", ""),
                    "uses_remaining": user.get("uses_remaining", 0),
                    "plan": user.get("plan", "free"),
                }
    return None


def get_user_by_email(email: str) -> dict | None:
    """Get user by email (without password data)."""
    email = email.strip().lower()
    with _lock:
        users = _load_users()
        user = users.get(email)
        if user:
            return {
                "id": user["id"],
                "email": user["email"],
                "display_name": user.get("display_name", ""),
                "uses_remaining": user.get("uses_remaining", 0),
                "plan": user.get("plan", "free"),
            }
    return None


def consume_use(user_id: str) -> int:
    """Atomically consume one use. Returns remaining uses, or -1 if none left."""
    with _lock:
        users = _load_users()
        for email, user in users.items():
            if user["id"] == user_id:
                remaining = user.get("uses_remaining", 0)
                if remaining <= 0:
                    return -1
                user["uses_remaining"] = remaining - 1
                _save_users(users)
                return user["uses_remaining"]
    return -1


def add_uses(user_id: str, count: int) -> int:
    """Add uses to a user account. Returns new remaining count."""
    with _lock:
        users = _load_users()
        for email, user in users.items():
            if user["id"] == user_id:
                user["uses_remaining"] = user.get("uses_remaining", 0) + count
                _save_users(users)
                return user["uses_remaining"]
    return -1


def reset_password(email: str, new_password: str) -> bool:
    """Reset a user's password. Returns True if user exists."""
    email = email.strip().lower()
    with _lock:
        users = _load_users()
        user = users.get(email)
        if not user:
            return False
        if len(new_password) < 6:
            raise ValueError("Password must be at least 6 characters.")
        pwd_hash, salt = _hash_password(new_password)
        user["password_hash"] = pwd_hash
        user["password_salt"] = salt
        _save_users(users)
    return True
