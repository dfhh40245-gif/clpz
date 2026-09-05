"""Unified authentication provider for CLPZ.

Routes to Supabase Auth (web) or local SQLite auth (desktop/dev)
based on configuration.

Desktop mode: local auth, no login required for processing.
Web mode: Supabase Auth, persistent sessions, email verification.
"""
from __future__ import annotations

import supabase_config
import auth
import database as db


def is_supabase_mode() -> bool:
    """Check if we're using Supabase auth (web mode)."""
    return supabase_config.is_configured()


# ── Signup ──────────────────────────────────────────────────────────

def signup(email: str, password: str, display_name: str = "") -> dict:
    """Create a new user account.

    Returns:
        {"id": str, "email": str, "display_name": str, "provider": "local"|"supabase"}
    """
    if is_supabase_mode():
        return _signup_supabase(email, password, display_name)
    return _signup_local(email, password, display_name)


def _signup_local(email: str, password: str, display_name: str) -> dict:
    """Local signup — uses SQLite."""
    user = auth.create_user(email, password, display_name)
    return {**user, "provider": "local"}


def _signup_supabase(email: str, password: str, display_name: str) -> dict:
    """Supabase signup — uses Supabase Auth."""
    client = supabase_config.get_supabase_client()
    if not client:
        raise RuntimeError("Supabase client unavailable")

    # Supabase Auth signup
    result = client.auth.sign_up({"email": email, "password": password})
    if result.user is None:
        raise ValueError("Signup failed — check email/password requirements")

    user_id = result.user.id

    # Create profile in Supabase database
    client.table("profiles").insert({
        "id": user_id,
        "email": email,
        "display_name": display_name or email.split("@")[0],
    }).execute()

    # Create initial credits
    import config
    client.table("credits").insert({
        "user_id": user_id,
        "balance": config.SIGNUP_BONUS,
    }).execute()

    # Record signup bonus transaction
    client.table("credit_transactions").insert({
        "user_id": user_id,
        "amount": config.SIGNUP_BONUS,
        "type": "signup_bonus",
        "reason": "Free credits on signup",
    }).execute()

    return {
        "id": user_id,
        "email": email,
        "display_name": display_name or email.split("@")[0],
        "provider": "supabase",
    }


# ── Login ───────────────────────────────────────────────────────────

def login(email: str, password: str) -> dict | None:
    """Authenticate a user. Returns user dict or None."""
    if is_supabase_mode():
        return _login_supabase(email, password)
    return _login_local(email, password)


def _login_local(email: str, password: str) -> dict | None:
    """Local login — uses SQLite."""
    return auth.authenticate_user(email, password)


def _login_supabase(email: str, password: str) -> dict | None:
    """Supabase login — uses Supabase Auth."""
    client = supabase_config.get_supabase_client()
    if not client:
        return None

    try:
        result = client.auth.sign_in_with_password({"email": email, "password": password})
        if result.user is None:
            return None

        # Get profile from database
        profile = client.table("profiles").select("*").eq("id", result.user.id).execute()
        if profile.data:
            p = profile.data[0]
            return {
                "id": result.user.id,
                "email": p.get("email", email),
                "display_name": p.get("display_name", ""),
                "provider": "supabase",
            }
        return {"id": result.user.id, "email": email, "display_name": "", "provider": "supabase"}
    except Exception:
        return None


# ── Session / Token ─────────────────────────────────────────────────

def create_session(user_id: str) -> str:
    """Create a session token."""
    if is_supabase_mode():
        return ""  # Supabase manages sessions via JWT
    return auth.create_session(user_id)


def validate_session(token: str) -> str | None:
    """Validate a session token. Returns user_id or None."""
    if is_supabase_mode():
        return _validate_supabase_session(token)
    return auth.validate_session(token)


def _validate_supabase_session(token: str) -> str | None:
    """Validate a Supabase JWT session."""
    client = supabase_config.get_supabase_client()
    if not client:
        return None

    try:
        # Verify the JWT token
        user = client.auth.get_user(token)
        if user and user.user:
            return user.user.id
    except Exception:
        pass
    return None


def destroy_session(token: str) -> None:
    """Destroy a session."""
    if is_supabase_mode():
        return  # Supabase manages sessions
    auth.destroy_session(token)


# ── User Info ───────────────────────────────────────────────────────

def get_user_by_id(user_id: str) -> dict | None:
    """Get user by ID."""
    if is_supabase_mode():
        return _get_user_supabase(user_id)
    return auth.get_user_by_id(user_id)


def _get_user_supabase(user_id: str) -> dict | None:
    """Get user from Supabase database."""
    client = supabase_config.get_supabase_client()
    if not client:
        return None

    profile = client.table("profiles").select("*").eq("id", user_id).execute()
    if profile.data:
        p = profile.data[0]
        return {
            "id": user_id,
            "email": p.get("email", ""),
            "display_name": p.get("display_name", ""),
            "provider": "supabase",
        }
    return None


def get_user_by_email(email: str) -> dict | None:
    """Get user by email."""
    if is_supabase_mode():
        client = supabase_config.get_supabase_client()
        if not client:
            return None
        profile = client.table("profiles").select("*").eq("email", email.strip().lower()).execute()
        if profile.data:
            p = profile.data[0]
            return {"id": p["id"], "email": p["email"], "display_name": p.get("display_name", ""), "provider": "supabase"}
        return None
    return auth.get_user_by_email(email)


# ── Password ────────────────────────────────────────────────────────

def set_password(user_id: str, new_password: str) -> None:
    """Set a new password."""
    if is_supabase_mode():
        raise NotImplementedError("Password change via Supabase requires client-side flow")
    auth.set_password(user_id, new_password)


def destroy_all_user_sessions(user_id: str) -> None:
    """Destroy all sessions for a user."""
    if is_supabase_mode():
        return  # Supabase manages sessions
    auth.destroy_all_user_sessions(user_id)


def reset_password(email: str, new_password: str) -> bool:
    """Reset a user's password."""
    if is_supabase_mode():
        raise NotImplementedError("Password reset via Supabase requires email flow")
    return auth.reset_password(email, new_password)


# ── Email Verification ──────────────────────────────────────────────

def generate_verification_code(user_id: str, purpose: str = "signup") -> str:
    """Generate a verification code."""
    if is_supabase_mode():
        return ""  # Supabase handles email verification
    return auth.generate_verification_code(user_id, purpose)


def verify_code(user_id: str, code: str, purpose: str = "signup") -> bool:
    """Verify a code."""
    if is_supabase_mode():
        return True  # Supabase handles verification
    return auth.verify_code(user_id, code, purpose)


def mark_email_verified(user_id: str) -> None:
    """Mark email as verified."""
    if is_supabase_mode():
        return  # Supabase handles verification
    auth.mark_email_verified(user_id)


def is_email_verified(user_id: str) -> bool:
    """Check if email is verified."""
    if is_supabase_mode():
        return True  # Supabase manages verification state
    return auth.is_email_verified(user_id)
