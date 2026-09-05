"""Supabase configuration for CLPZ web mode.

When NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set,
the web application uses Supabase for auth and database.

When not set, the application falls back to local SQLite auth
(desktop mode or development without Supabase).

NEVER put service_role keys in frontend code.
NEVER log authentication secrets.
"""
from __future__ import annotations

import os


def _get_env(key: str, default: str = "") -> str:
    """Get an environment variable."""
    return os.getenv(key, default)


# Public anon key (safe for frontend)
SUPABASE_URL = _get_env("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_ANON_KEY = _get_env("NEXT_PUBLIC_SUPABASE_ANON_KEY")

# Service role key (SERVER-SIDE ONLY — never expose to frontend)
SUPABASE_SERVICE_ROLE_KEY = _get_env("SUPABASE_SERVICE_ROLE_KEY")


def is_configured() -> bool:
    """Check if Supabase is properly configured with real credentials."""
    return (
        bool(SUPABASE_URL)
        and bool(SUPABASE_SERVICE_ROLE_KEY)
        and "YOUR_" not in SUPABASE_URL  # Exclude placeholder values
        and "YOUR_" not in SUPABASE_SERVICE_ROLE_KEY
    )


def get_supabase_client():
    """Get a Supabase client with service role privileges (server-side only).

    Returns None if Supabase is not configured.
    """
    if not is_configured():
        return None

    try:
        from supabase import create_client, Client
        client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        return client
    except ImportError:
        # supabase-py not installed — fall back to local
        return None
    except Exception:
        return None


def get_supabase_anon_client():
    """Get a Supabase client with anon key (for operations that don't need service role).

    Returns None if Supabase is not configured.
    """
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None
    if "YOUR_" in SUPABASE_URL:
        return None

    try:
        from supabase import create_client, Client
        client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        return client
    except ImportError:
        return None
    except Exception:
        return None
