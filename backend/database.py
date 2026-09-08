"""SQLite database layer for CLPZ.

Replaces JSON-file storage for users, sessions, credits, and credit
transactions.  Jobs metadata is also stored here but heavy pipeline
state (video files, rendered clips) stays on disk in data/<job_id>/.

Uses WAL journal mode for safe concurrent reads.  A single threading
lock serialises writes.  SQLite's atomic transactions prevent corruption
even on power loss.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

import config

_DB_PATH = config.DATA_DIR / "clpz.db"
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

# ── Connection management ──────────────────────────────────────────


def _get_conn() -> sqlite3.Connection:
    """Return the module-level connection, creating it on first call."""
    global _conn
    if _conn is not None:
        return _conn
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(_DB_PATH), timeout=10, check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _conn.execute("PRAGMA busy_timeout=5000")
    _conn.row_factory = sqlite3.Row
    _init_schema(_conn)
    return _conn


def _safe_commit(conn: sqlite3.Connection) -> None:
    """Commit, rolling back on failure so a write transaction is never left
    dangling (a dangling transaction would block every later writer)."""
    try:
        conn.commit()
    except sqlite3.Error:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        raise


from contextlib import contextmanager as _contextmanager


@_contextmanager
def _write():
    """Exclusive DB access with guaranteed commit-or-rollback on exit.

    Every mutation goes through this: if any statement inside the block
    raises (e.g. a foreign-key violation or a busy timeout), the open
    transaction is rolled back instead of left dangling.  A dangling write
    transaction on the shared connection would block every later writer —
    including other processes — with 'database is locked' forever.
    """
    with _lock:
        conn = _get_conn()
        try:
            yield conn
            conn.commit()
        except BaseException:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise


def close() -> None:
    """Close the database connection (for clean shutdown)."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


# ── Schema ─────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    email_verified INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free'
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);

CREATE TABLE IF NOT EXISTS credits (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS credit_transactions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    type TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    related_id TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_txns_user ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_txns_created ON credit_transactions(created_at);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    input_type TEXT NOT NULL DEFAULT 'youtube',
    url TEXT NOT NULL DEFAULT '',
    stage TEXT NOT NULL DEFAULT 'queued',
    progress REAL NOT NULL DEFAULT 0.0,
    created_at REAL,
    started_at REAL,
    completed_at REAL,
    failed_at REAL,
    cancelled_at REAL,
    max_clips INTEGER NOT NULL DEFAULT 5,
    top_text TEXT NOT NULL DEFAULT '',
    error TEXT,
    error_code TEXT,
    completed_stages TEXT NOT NULL DEFAULT '[]',
    video TEXT NOT NULL DEFAULT '{}',
    clips TEXT NOT NULL DEFAULT '[]',
    timings TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_stage ON jobs(stage);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);

CREATE TABLE IF NOT EXISTS verification_codes (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    purpose TEXT NOT NULL,
    expires_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_idemp_user ON idempotency_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_idemp_created ON idempotency_keys(created_at);

CREATE TABLE IF NOT EXISTS idempotency_jobs (
    key TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    user_id TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_idemjob_created ON idempotency_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_idemjob_job ON idempotency_jobs(job_id);

CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'gumroad',
    external_id TEXT NOT NULL,
    product_id TEXT NOT NULL DEFAULT '',
    amount_cents INTEGER NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'usd',
    status TEXT NOT NULL DEFAULT 'paid',
    raw_json TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    UNIQUE (provider, external_id)
);
CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_external ON payments(provider, external_id);
"""

# Lightweight ordered migrations.  ``PRAGMA user_version`` is the applied
# schema version; each entry is applied in order and idempotently.
_MIGRATIONS: list[str] = []


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist, then apply ordered migrations."""
    conn.executescript(_SCHEMA)
    _apply_migrations(conn)
    _safe_commit(conn)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply ``_MIGRATIONS`` entries above the current ``user_version``."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for idx in range(current, len(_MIGRATIONS)):
        conn.executescript(_MIGRATIONS[idx])
        conn.execute(f"PRAGMA user_version = {idx + 1}")
        _safe_commit(conn)


def schema_version() -> int:
    """Return the current applied schema version."""
    with _write() as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


# ── Users ──────────────────────────────────────────────────────────


def create_user(user_id: str, email: str, password_hash: str, salt: str,
                display_name: str = "", created_at: float = 0) -> dict:
    """Insert a new user. Raises sqlite3.IntegrityError on duplicate email."""
    created_at = created_at or time.time()
    with _write() as conn:
        conn.execute(
            "INSERT INTO users (id, email, display_name, password_hash, password_salt, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email.lower(), display_name, password_hash, salt, created_at),
        )
        _safe_commit(conn)
    return {"id": user_id, "email": email.lower(), "display_name": display_name}


def get_user_by_email(email: str) -> dict | None:
    """Return user dict (without password fields) or None."""
    with _write() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "email_verified": bool(row["email_verified"]),
        "plan": row["plan"],
    }


def get_user_by_id(user_id: str) -> dict | None:
    """Return user dict (without password fields) or None."""
    with _write() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "email_verified": bool(row["email_verified"]),
        "plan": row["plan"],
    }


def get_user_password(email: str) -> dict | None:
    """Return {id, password_hash, password_salt} for authentication, or None."""
    with _write() as conn:
        row = conn.execute(
            "SELECT id, password_hash, password_salt FROM users WHERE email = ?",
            (email.lower(),),
        ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "password_hash": row["password_hash"], "password_salt": row["password_salt"]}


def set_password(user_id: str, password_hash: str, salt: str) -> None:
    """Update a user's password hash and salt."""
    with _write() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
            (password_hash, salt, user_id),
        )
        _safe_commit(conn)


def mark_email_verified(user_id: str) -> None:
    """Mark a user's email as verified."""
    with _write() as conn:
        conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user_id,))
        _safe_commit(conn)


def is_email_verified(user_id: str) -> bool:
    """Check if a user's email is verified."""
    with _write() as conn:
        row = conn.execute("SELECT email_verified FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row["email_verified"]) if row else False


def user_exists(email: str) -> bool:
    """Check if an email is already registered."""
    with _write() as conn:
        row = conn.execute("SELECT 1 FROM users WHERE email = ?", (email.lower(),)).fetchone()
    return row is not None


# ── Sessions ───────────────────────────────────────────────────────

_MAX_SESSION_AGE = 86400 * 7  # 7 days


def create_session(user_id: str) -> str:
    """Create a session token. Returns the token string."""
    import secrets as _secrets
    token = _secrets.token_urlsafe(32)
    with _write() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, time.time()),
        )
        _safe_commit(conn)
    return token


def validate_session(token: str) -> str | None:
    """Validate a session token. Returns user_id or None."""
    if not token:
        return None
    with _write() as conn:
        row = conn.execute(
            "SELECT user_id, created_at FROM sessions WHERE token = ?", (token,)
        ).fetchone()
    if not row:
        return None
    if time.time() - row["created_at"] > _MAX_SESSION_AGE:
        destroy_session(token)
        return None
    return row["user_id"]


def destroy_session(token: str) -> None:
    """Destroy a single session."""
    with _write() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        _safe_commit(conn)


def destroy_all_user_sessions(user_id: str) -> None:
    """Destroy all sessions for a user (force re-login)."""
    with _write() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        _safe_commit(conn)


def cleanup_expired_sessions() -> int:
    """Remove expired sessions. Returns count deleted."""
    cutoff = time.time() - _MAX_SESSION_AGE
    with _write() as conn:
        cursor = conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))
        _safe_commit(conn)
    return cursor.rowcount


# ── Credits ────────────────────────────────────────────────────────


def get_credit_balance(user_id: str) -> int:
    """Return current credit balance (always >= 0)."""
    with _write() as conn:
        row = conn.execute("SELECT balance FROM credits WHERE user_id = ?", (user_id,)).fetchone()
    return max(0, row["balance"]) if row else 0


def set_credit_balance(user_id: str, balance: int) -> None:
    """Set credit balance directly (for migrations)."""
    with _write() as conn:
        conn.execute(
            "INSERT INTO credits (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance",
            (user_id, balance),
        )
        _safe_commit(conn)


def check_and_charge(user_id: str, amount: int, related_id: str = "") -> tuple[bool, int]:
    """Atomically check balance and deduct credits.

    Returns (success, remaining_balance).
    If balance is insufficient, no deduction occurs and success=False.
    """
    if amount <= 0:
        return True, get_credit_balance(user_id)

    with _write() as conn:
        row = conn.execute("SELECT balance FROM credits WHERE user_id = ?", (user_id,)).fetchone()
        current = max(0, row["balance"]) if row else 0

        if current < amount:
            return False, current

        new_balance = current - amount
        conn.execute(
            "INSERT INTO credits (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance",
            (user_id, new_balance),
        )
        _log_txn(conn, user_id, -amount, "forge",
                 f"Forge clip generation ({amount} credit{'s' if amount != 1 else ''})",
                 related_id=related_id)
        _safe_commit(conn)
    return True, new_balance


def refund_credits(user_id: str, amount: int, related_id: str = "", reason: str = "") -> int:
    """Refund credits (e.g. on pipeline failure). Returns new balance."""
    if amount <= 0:
        return get_credit_balance(user_id)

    with _write() as conn:
        row = conn.execute("SELECT balance FROM credits WHERE user_id = ?", (user_id,)).fetchone()
        current = max(0, row["balance"]) if row else 0
        new_balance = current + amount
        conn.execute(
            "INSERT INTO credits (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance",
            (user_id, new_balance),
        )
        _log_txn(conn, user_id, amount, "refund",
                 reason or "Refund for failed processing",
                 related_id=related_id)
        _safe_commit(conn)
    return new_balance


def subtract_credits(user_id: str, amount: int, related_id: str = "",
                     reason: str = "") -> int:
    """Subtract credits (e.g. Gumroad purchase reversal). Never below zero.

    Logs a negative transaction so the ledger stays auditable.
    """
    if amount <= 0:
        return get_credit_balance(user_id)

    with _write() as conn:
        row = conn.execute("SELECT balance FROM credits WHERE user_id = ?", (user_id,)).fetchone()
        current = max(0, row["balance"]) if row else 0
        new_balance = max(0, current - amount)
        conn.execute(
            "INSERT INTO credits (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance",
            (user_id, new_balance),
        )
        _log_txn(conn, user_id, -amount, "refund",
                 reason or "Refund (purchase reversal)",
                 related_id=related_id)
        _safe_commit(conn)
    return new_balance


def add_credits(user_id: str, amount: int, txn_type: str = "purchase",
                description: str = "") -> int:
    """Add credits. Returns new balance."""
    if amount <= 0:
        return get_credit_balance(user_id)

    with _write() as conn:
        row = conn.execute("SELECT balance FROM credits WHERE user_id = ?", (user_id,)).fetchone()
        current = max(0, row["balance"]) if row else 0
        new_balance = current + amount
        conn.execute(
            "INSERT INTO credits (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance",
            (user_id, new_balance),
        )
        _log_txn(conn, user_id, amount, txn_type,
                 description or f"Credits added ({amount})")
        _safe_commit(conn)
    return new_balance


# ── Credit Transactions ────────────────────────────────────────────


def _log_txn(conn: sqlite3.Connection, user_id: str, amount: int,
             txn_type: str, description: str = "", related_id: str = "") -> None:
    """Log a credit transaction (caller must hold _lock and have active conn)."""
    import secrets as _secrets
    txn_id = _secrets.token_hex(8)
    conn.execute(
        "INSERT INTO credit_transactions (id, user_id, amount, type, description, related_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (txn_id, user_id, amount, txn_type, description, related_id or "", time.time()),
    )


def log_transaction(user_id: str, amount: int, txn_type: str,
                    description: str = "", related_id: str = "") -> None:
    """Public wrapper to log a credit transaction."""
    with _write() as conn:
        _log_txn(conn, user_id, amount, txn_type, description, related_id)
        _safe_commit(conn)


def get_transactions(user_id: str, limit: int = 50) -> list[dict]:
    """Return recent transactions for a user (newest first)."""
    with _write() as conn:
        rows = conn.execute(
            "SELECT * FROM credit_transactions WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def has_signup_bonus(user_id: str) -> bool:
    """Check if a user has ever received a signup bonus."""
    with _write() as conn:
        row = conn.execute(
            "SELECT 1 FROM credit_transactions WHERE user_id = ? AND type = 'signup_bonus' LIMIT 1",
            (user_id,),
        ).fetchone()
    return row is not None


# ── Jobs ───────────────────────────────────────────────────────────


def has_refund_for_job(related_id: str) -> bool:
    """Check if a refund was already issued for a specific job/order."""
    if not related_id:
        return False
    with _write() as conn:
        row = conn.execute(
            "SELECT 1 FROM credit_transactions WHERE related_id = ? AND type = 'refund' LIMIT 1",
            (related_id,),
        ).fetchone()
    return row is not None

def save_job(job: dict) -> None:
    """Insert or update a job in the database."""
    with _write() as conn:
        conn.execute(
            "INSERT INTO jobs (id, user_id, input_type, url, stage, progress, "
            "created_at, started_at, completed_at, failed_at, cancelled_at, "
            "max_clips, top_text, error, error_code, completed_stages, "
            "video, clips, timings) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "user_id=excluded.user_id, stage=excluded.stage, progress=excluded.progress, "
            "started_at=excluded.started_at, completed_at=excluded.completed_at, "
            "failed_at=excluded.failed_at, cancelled_at=excluded.cancelled_at, "
            "error=excluded.error, error_code=excluded.error_code, "
            "completed_stages=excluded.completed_stages, "
            "video=excluded.video, clips=excluded.clips, timings=excluded.timings",
            (
                job.get("id"),
                job.get("user_id"),
                job.get("input_type", "youtube"),
                job.get("url", ""),
                job.get("stage", "queued"),
                job.get("progress", 0.0),
                job.get("created_at"),
                job.get("started_at"),
                job.get("completed_at"),
                job.get("failed_at"),
                job.get("cancelled_at"),
                job.get("max_clips", 5),
                job.get("top_text", ""),
                job.get("error"),
                job.get("error_code"),
                json.dumps(job.get("completed_stages", [])),
                json.dumps(job.get("video", {})),
                json.dumps(job.get("clips", [])),
                json.dumps(job.get("timings", {})),
            ),
        )
        _safe_commit(conn)


def get_job(job_id: str) -> dict | None:
    """Return a job dict or None."""
    with _write() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    return _row_to_job(row)


def get_all_jobs() -> list[dict]:
    """Return all jobs (newest first)."""
    with _write() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [_row_to_job(r) for r in rows]


def update_job(job_id: str, **kwargs) -> None:
    """Update specific fields of a job."""
    with _write() as conn:
        sets = []
        vals = []
        for key, val in kwargs.items():
            if key in ("completed_stages", "video", "clips", "timings"):
                val = json.dumps(val)
            sets.append(f"{key} = ?")
            vals.append(val)
        vals.append(job_id)
        conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", vals)
        _safe_commit(conn)


def delete_job(job_id: str) -> None:
    """Delete a job record."""
    with _write() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        _safe_commit(conn)


def count_user_jobs(user_id: str, stage: str | None = None) -> int:
    """Count jobs for a user, optionally filtered by stage."""
    with _write() as conn:
        if stage:
            row = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE user_id = ? AND stage = ?",
                (user_id, stage),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE user_id = ?", (user_id,)
            ).fetchone()
    return row[0] if row else 0


def _row_to_job(row: sqlite3.Row) -> dict:
    """Convert a database row to a job dict."""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "input_type": row["input_type"],
        "url": row["url"],
        "stage": row["stage"],
        "progress": row["progress"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "failed_at": row["failed_at"],
        "cancelled_at": row["cancelled_at"],
        "max_clips": row["max_clips"],
        "top_text": row["top_text"],
        "error": row["error"],
        "error_code": row["error_code"],
        "completed_stages": json.loads(row["completed_stages"]) if row["completed_stages"] else [],
        "video": json.loads(row["video"]) if row["video"] else {},
        "clips": json.loads(row["clips"]) if row["clips"] else [],
        "timings": json.loads(row["timings"]) if row["timings"] else {},
    }


# ── Verification Codes ─────────────────────────────────────────────


def save_verification_code(user_id: str, code: str, purpose: str, expires_at: float) -> None:
    """Save a verification code for a user."""
    with _write() as conn:
        conn.execute(
            "INSERT INTO verification_codes (user_id, code, purpose, expires_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET code=excluded.code, "
            "purpose=excluded.purpose, expires_at=excluded.expires_at",
            (user_id, code, purpose, expires_at),
        )
        _safe_commit(conn)


def get_verification_code(user_id: str) -> dict | None:
    """Get the active verification code for a user, or None if expired/missing."""
    with _write() as conn:
        row = conn.execute(
            "SELECT code, purpose, expires_at FROM verification_codes WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    if time.time() > row["expires_at"]:
        delete_verification_code(user_id)
        return None
    return {"code": row["code"], "purpose": row["purpose"], "expires_at": row["expires_at"]}


def delete_verification_code(user_id: str) -> None:
    """Delete a verification code for a user."""
    with _write() as conn:
        conn.execute("DELETE FROM verification_codes WHERE user_id = ?", (user_id,))
        _safe_commit(conn)


def verify_code(user_id: str, code: str, purpose: str) -> bool:
    """Verify a code. Returns True if valid and deletes it (one-time use)."""
    import secrets as _secrets
    stored = get_verification_code(user_id)
    if not stored:
        return False
    if stored["purpose"] != purpose:
        return False
    if not _secrets.compare_digest(stored["code"], code.strip()):
        return False
    delete_verification_code(user_id)
    return True



# ── Idempotency ───────────────────────────────────────────────────


def check_idempotency(key: str) -> dict | None:
    """Check if an idempotency key already has a result.

    Returns the stored result dict if found and not expired, or None.
    Keys expire after 24 hours.
    """
    if not key:
        return None
    with _write() as conn:
        row = conn.execute(
            "SELECT result, created_at FROM idempotency_keys WHERE key = ?",
            (key,),
        ).fetchone()
    if not row:
        return None
    if time.time() - row["created_at"] > 86400:
        # Expired — clean up
        delete_idempotency(key)
        return None
    return json.loads(row["result"])


def save_idempotency(key: str, user_id: str, operation: str, result: dict) -> None:
    """Save an idempotency key with its result."""
    with _write() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO idempotency_keys (key, user_id, operation, result, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (key, user_id, operation, json.dumps(result), time.time()),
        )
        _safe_commit(conn)


def delete_idempotency(key: str) -> None:
    """Delete an idempotency key."""
    with _write() as conn:
        conn.execute("DELETE FROM idempotency_keys WHERE key = ?", (key,))
        _safe_commit(conn)


def cleanup_old_idempotency() -> int:
    """Remove expired idempotency keys and job mappings. Returns count deleted."""
    cutoff = time.time() - 86400
    with _write() as conn:
        c1 = conn.execute("DELETE FROM idempotency_keys WHERE created_at < ?", (cutoff,))
        c2 = conn.execute("DELETE FROM idempotency_jobs WHERE created_at < ?", (cutoff,))
        _safe_commit(conn)
    return c1.rowcount + c2.rowcount


# ── Idempotency → job mapping (one logical submit = one job) ─────────


def get_job_id_for_idempotency(key: str) -> str | None:
    """Return the job_id previously created for an idempotency key, if any."""
    if not key:
        return None
    with _write() as conn:
        row = conn.execute(
            "SELECT job_id FROM idempotency_jobs WHERE key = ?", (key,),
        ).fetchone()
    return row["job_id"] if row else None


def save_idempotency_job(key: str, job_id: str, user_id: str | None) -> None:
    """Atomically record that an idempotency key maps to a created job."""
    with _write() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO idempotency_jobs (key, job_id, user_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (key, job_id, user_id, time.time()),
        )
        _safe_commit(conn)


def delete_idempotency_job_by_key(key: str) -> None:
    """Remove an idempotency→job mapping (used when a job is hard-deleted)."""
    if not key:
        return
    with _write() as conn:
        conn.execute("DELETE FROM idempotency_jobs WHERE key = ?", (key,))
        _safe_commit(conn)


def delete_idempotency_jobs_by_job(job_id: str) -> None:
    """Remove every idempotency→job mapping pointing at a deleted job."""
    if not job_id:
        return
    with _write() as conn:
        conn.execute("DELETE FROM idempotency_jobs WHERE job_id = ?", (job_id,))
        _safe_commit(conn)


# ── Admin helpers ─────────────────────────────────────────────────


def get_all_users(limit: int = 100, offset: int = 0) -> list[dict]:
    """Return all users (for admin)."""
    with _write() as conn:
        rows = conn.execute(
            "SELECT id, email, display_name, email_verified, created_at, plan "
            "FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def count_users() -> int:
    """Count total users."""
    with _write() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def set_user_plan(user_id: str, plan: str) -> None:
    """Update a user's plan (admin)."""
    with _write() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
        _safe_commit(conn)



# ── Migration helpers ──────────────────────────────────────────────


def migrate_from_json() -> None:
    """One-time migration from JSON files to SQLite.

    Safe to call multiple times — skips already-migrated data.
    """
    from pathlib import Path as _P

    # Migrate users
    users_file = config.DATA_DIR / "users.json"
    if users_file.exists():
        try:
            old_users = json.loads(users_file.read_text(encoding="utf-8"))
            conn = _get_conn()
            migrated = 0
            for email, user in old_users.items():
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO users "
                        "(id, email, display_name, password_hash, password_salt, email_verified, created_at, plan) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            user["id"],
                            email,
                            user.get("display_name", ""),
                            user["password_hash"],
                            user["password_salt"],
                            1 if user.get("email_verified") else 0,
                            user.get("created_at", 0),
                            user.get("plan", "free"),
                        ),
                    )
                    migrated += 1
                except sqlite3.IntegrityError:
                    pass
            _safe_commit(conn)
            if migrated:
                print(f"  Migrated {migrated} user(s) from users.json")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  Warning: Could not migrate users.json: {e}")

    # Migrate credits
    credits_file = config.DATA_DIR / "credits.json"
    if credits_file.exists():
        try:
            old_credits = json.loads(credits_file.read_text(encoding="utf-8"))
            conn = _get_conn()
            migrated = 0
            for user_id, balance in old_credits.items():
                conn.execute(
                    "INSERT OR IGNORE INTO credits (user_id, balance) VALUES (?, ?)",
                    (user_id, balance),
                )
                migrated += 1
            _safe_commit(conn)
            if migrated:
                print(f"  Migrated {migrated} credit balance(s) from credits.json")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  Warning: Could not migrate credits.json: {e}")

    # Migrate credit transactions
    txns_file = config.DATA_DIR / "credit_transactions.json"
    if txns_file.exists():
        try:
            old_txns = json.loads(txns_file.read_text(encoding="utf-8"))
            conn = _get_conn()
            migrated = 0
            for txn in old_txns:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO credit_transactions "
                        "(id, user_id, amount, type, description, related_id, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            txn["id"],
                            txn["user_id"],
                            txn["amount"],
                            txn["type"],
                            txn.get("description", ""),
                            txn.get("related_id", ""),
                            txn.get("created_at", 0),
                        ),
                    )
                    migrated += 1
                except (sqlite3.IntegrityError, KeyError):
                    pass
            _safe_commit(conn)
            if migrated:
                print(f"  Migrated {migrated} transaction(s) from credit_transactions.json")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  Warning: Could not migrate credit_transactions.json: {e}")

    # Migrate sessions
    sessions_file = config.DATA_DIR / "sessions.json"
    if sessions_file.exists():
        try:
            old_sessions = json.loads(sessions_file.read_text(encoding="utf-8"))
            conn = _get_conn()
            migrated = 0
            now = time.time()
            for token, session in old_sessions.items():
                # Only migrate non-expired sessions
                if now - session.get("created_at", 0) < _MAX_SESSION_AGE:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                            (token, session["user_id"], session.get("created_at", 0)),
                        )
                        migrated += 1
                    except sqlite3.IntegrityError:
                        pass
            _safe_commit(conn)
            if migrated:
                print(f"  Migrated {migrated} session(s) from sessions.json")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  Warning: Could not migrate sessions.json: {e}")

    # Migrate jobs from data/<job_id>/job.json
    data_dir = config.DATA_DIR
    migrated_jobs = 0
    for job_dir in data_dir.iterdir():
        if not job_dir.is_dir():
            continue
        if job_dir.name == "__pycache__" or job_dir.name.startswith("."):
            continue
        job_file = job_dir / "job.json"
        if not job_file.exists():
            continue
        try:
            job = json.loads(job_file.read_text(encoding="utf-8"))
            conn = _get_conn()
            conn.execute(
                "INSERT OR IGNORE INTO jobs "
                "(id, user_id, input_type, url, stage, progress, "
                "created_at, started_at, completed_at, failed_at, cancelled_at, "
                "max_clips, top_text, error, error_code, completed_stages, "
                "video, clips, timings) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job.get("id"),
                    job.get("user_id"),
                    job.get("input_type", "youtube"),
                    job.get("url", ""),
                    job.get("stage", "queued"),
                    job.get("progress", 0.0),
                    job.get("created_at"),
                    job.get("started_at"),
                    job.get("completed_at"),
                    job.get("failed_at"),
                    job.get("cancelled_at"),
                    job.get("max_clips", 5),
                    job.get("top_text", ""),
                    job.get("error"),
                    job.get("error_code"),
                    json.dumps(job.get("completed_stages", [])),
                    json.dumps(job.get("video", {})),
                    json.dumps(job.get("clips", [])),
                    json.dumps(job.get("timings", {})),
                ),
            )
            _safe_commit(conn)
            migrated_jobs += 1
        except (json.JSONDecodeError, OSError, sqlite3.IntegrityError) as e:
            print(f"  Warning: Could not migrate job {job_dir.name}: {e}")
    if migrated_jobs:
        print(f"  Migrated {migrated_jobs} job(s) from data directories")


def backup_database() -> Path | None:
    """Create a backup of the database. Returns backup path."""
    import shutil as _shutil
    if not _DB_PATH.exists():
        return None
    backup = _DB_PATH.with_suffix(".db.bak")
    with _write() as conn:
        conn.execute(f"VACUUM INTO '{str(backup)}'")
    return backup


def get_stats() -> dict:
    """Return database statistics."""
    with _write() as conn:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        credit_rows = conn.execute("SELECT COUNT(*) FROM credits").fetchone()[0]
        txns = conn.execute("SELECT COUNT(*) FROM credit_transactions").fetchone()[0]
        jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        payments = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    return {
        "users": users,
        "sessions": sessions,
        "credit_accounts": credit_rows,
        "transactions": txns,
        "jobs": jobs,
        "payments": payments,
        "db_size_mb": round(_DB_PATH.stat().st_size / 1024 / 1024, 2) if _DB_PATH.exists() else 0,
    }


# ── Payments (Gumroad & other providers) ──────────────────────────


def record_payment(user_id: str | None, provider: str, external_id: str,
                   product_id: str = "", amount_cents: int = 0,
                   currency: str = "usd", status: str = "paid",
                   raw_json: str = "") -> tuple[bool, str]:
    """Record an external payment exactly once.

    Returns (created, payment_id). If a payment with the same
    (provider, external_id) already exists, returns (False, existing_id)
    and does NOT modify anything — this is the idempotency guard that
    prevents duplicate webhooks from granting credits twice.

    user_id may be None for purchases that could not be linked to a CLPZ
    account (audit trail only, no FK enforced).
    """
    import secrets as _secrets
    payment_id = _secrets.token_hex(8)
    with _write() as conn:
        existing = conn.execute(
            "SELECT id FROM payments WHERE provider = ? AND external_id = ?",
            (provider, external_id),
        ).fetchone()
        if existing:
            return False, existing["id"]
        conn.execute(
            "INSERT INTO payments (id, user_id, provider, external_id, product_id, "
            "amount_cents, currency, status, raw_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (payment_id, user_id, provider, external_id, product_id,
             amount_cents, currency, status, raw_json, time.time()),
        )
        _safe_commit(conn)
    return True, payment_id


def get_payment(provider: str, external_id: str) -> dict | None:
    """Look up a payment by provider + external id."""
    with _write() as conn:
        row = conn.execute(
            "SELECT * FROM payments WHERE provider = ? AND external_id = ?",
            (provider, external_id),
        ).fetchone()
    return dict(row) if row else None


def update_payment_status(provider: str, external_id: str, status: str) -> bool:
    """Transition a payment's status (e.g. paid -> refunded).

    Returns True if the status actually changed, False if it was already
    in the target state (idempotent transition — safe on duplicate
    refund/chargeback webhooks).
    """
    with _write() as conn:
        row = conn.execute(
            "SELECT id, status FROM payments WHERE provider = ? AND external_id = ?",
            (provider, external_id),
        ).fetchone()
        if not row or row["status"] == status:
            return False
        conn.execute(
            "UPDATE payments SET status = ? WHERE provider = ? AND external_id = ?",
            (status, provider, external_id),
        )
        _safe_commit(conn)
    return True


def get_user_payments(user_id: str, limit: int = 50) -> list[dict]:
    """Return payments for a user (newest first)."""
    with _write() as conn:
        rows = conn.execute(
            "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]
