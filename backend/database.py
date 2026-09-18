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
    conn = sqlite3.connect(str(_DB_PATH), timeout=10, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        _init_schema(conn)
    except BaseException:
        conn.rollback()
        conn.close()
        raise
    _conn = conn
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

-- Task 16: device-link exchange codes. A signed-in WEBSITE/owner session
-- creates a one-use, short-lived code bound to a random state; the DESKTOP
-- redeems code+state exactly once. Replay (second redemption of the same
-- code) fails because redemption consumes the row atomically.
CREATE TABLE IF NOT EXISTS device_link_codes (
    code TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    used_at REAL
);

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
    timings TEXT NOT NULL DEFAULT '{}',
    edit_versions TEXT NOT NULL DEFAULT '[]'
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
    -- Task 09: scoped to principal/workspace. PK (scope, key) so two
    -- principals reusing one key string never overwrite each other.
    scope TEXT NOT NULL DEFAULT '',
    key TEXT NOT NULL,
    job_id TEXT NOT NULL,
    user_id TEXT,
    created_at REAL NOT NULL,
    fingerprint TEXT,
    PRIMARY KEY (scope, key)
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
# Lightweight ordered migrations. ``PRAGMA user_version`` is the applied
# schema version; each entry is applied in order and is IDEMPOTENT, so a
# database from any earlier development iteration converges to the current
# schema without failing (task 09 hardening: version markers can drift while
# a migration set is being developed; shipped releases only ever move forward).
def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _pk_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Columns participating in the table's PRIMARY KEY (pk position > 0)."""
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall() if r[5] > 0}


def _migrate_v1_role(conn: sqlite3.Connection) -> None:
    """v1: role column for trusted admin provisioning (task 04). Admin
    rights are an immutable server-side attribute of a provisioned user ID,
    never derived from a configured email string."""
    if "role" not in _columns(conn, "users"):
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")


def _migrate_v2_payment_amounts(conn: sqlite3.Connection) -> None:
    """v2 (task 08): persist the actual credited amounts on a payment so a
    reversal reverses what was really granted, not a recomputed value.
    NULL credits_granted marks a payment that was recorded but whose
    fulfillment (credit grant) never completed — replay completes it
    exactly once. Legacy rows stay NULL: their original amount is unknown,
    so reversals fall back to the configured product mapping."""
    cols = _columns(conn, "payments")
    if "credits_granted" not in cols:
        conn.execute("ALTER TABLE payments ADD COLUMN credits_granted INTEGER")
    if "credits_reversed" not in cols:
        conn.execute(
            "ALTER TABLE payments ADD COLUMN credits_reversed INTEGER NOT NULL DEFAULT 0")


def _migrate_v3_scoped_idempotency(conn: sqlite3.Connection) -> None:
    """v3 (task 09): scope idempotency-job mappings to principal+operation
    and record the canonical request fingerprint.

    The legacy table's PRIMARY KEY was ``key`` ALONE, so two principals
    reusing one key string overwrote each other's mapping (cross-owner
    replay, F09). The PK must become (scope, key), which requires a table
    rebuild in SQLite. Idempotent: any legacy shape is rebuilt exactly to
    the new shape; an already-rebuilt table is left untouched."""
    if "idempotency_jobs" not in {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }:
        return  # Fresh schema creates the scoped table directly.
    if "scope" not in _columns(conn, "idempotency_jobs"):
        conn.execute(
            "ALTER TABLE idempotency_jobs ADD COLUMN scope TEXT NOT NULL DEFAULT ''")
    if "fingerprint" not in _columns(conn, "idempotency_jobs"):
        conn.execute("ALTER TABLE idempotency_jobs ADD COLUMN fingerprint TEXT")
    pk = _pk_columns(conn, "idempotency_jobs")
    if pk == {"scope", "key"}:
        return  # Already rebuilt (fresh schema or previous run).

    conn.execute(
        """CREATE TABLE idempotency_jobs_rebuild (
            scope TEXT NOT NULL DEFAULT '',
            key TEXT NOT NULL,
            job_id TEXT NOT NULL,
            user_id TEXT,
            created_at REAL NOT NULL,
            fingerprint TEXT,
            PRIMARY KEY (scope, key)
        )""")
    # OR REPLACE dedupes legacy rows that repeated the same key.
    conn.execute(
        "INSERT OR REPLACE INTO idempotency_jobs_rebuild "
        "(scope, key, job_id, user_id, created_at, fingerprint) "
        "SELECT scope, key, job_id, user_id, created_at, fingerprint "
        "FROM idempotency_jobs")
    conn.execute("DROP TABLE idempotency_jobs")
    conn.execute("ALTER TABLE idempotency_jobs_rebuild RENAME TO idempotency_jobs")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_idemjob_created ON idempotency_jobs(created_at)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_idemjob_job ON idempotency_jobs(job_id)")


def _migrate_v4_edit_versions(conn: sqlite3.Connection) -> None:
    """Move legacy edit history from snapshots into the authoritative store.

    Existing SQLite rows import only the previously unpersisted edit field.
    JSON-only legacy projects are imported once when SQLite authority begins.
    The migration and schema marker commit together, making crash retry safe.
    """
    if "edit_versions" not in _columns(conn, "jobs"):
        conn.execute("ALTER TABLE jobs ADD COLUMN edit_versions TEXT NOT NULL DEFAULT '[]'")
    known_ids = {row["id"] for row in conn.execute("SELECT id FROM jobs").fetchall()}
    for snapshot in config.DATA_DIR.glob("*/job.json"):
        job_id = snapshot.parent.name
        try:
            legacy = json.loads(snapshot.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(legacy, dict) or legacy.get("id") != job_id:
            continue
        versions = legacy.get("edit_versions", [])
        if not isinstance(versions, list) or not all(isinstance(v, dict) for v in versions):
            continue
        if job_id not in known_ids:
            conn.execute(
                "INSERT INTO jobs (id, user_id, input_type, url, stage, progress, "
                "created_at, started_at, completed_at, failed_at, cancelled_at, "
                "max_clips, top_text, error, error_code, completed_stages, "
                "video, clips, timings, edit_versions) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, legacy.get("user_id"), legacy.get("input_type", "youtube"),
                 legacy.get("url", ""), legacy.get("stage", "queued"),
                 legacy.get("progress", 0.0), legacy.get("created_at"),
                 legacy.get("started_at"), legacy.get("completed_at"),
                 legacy.get("failed_at"), legacy.get("cancelled_at"),
                 legacy.get("max_clips", 5), legacy.get("top_text", ""),
                 legacy.get("error"), legacy.get("error_code"),
                 json.dumps(legacy.get("completed_stages", [])),
                 json.dumps(legacy.get("video", {})),
                 json.dumps(legacy.get("clips", [])),
                 json.dumps(legacy.get("timings", {})),
                 json.dumps(versions)),
            )
            known_ids.add(job_id)
            continue
        if versions:
            conn.execute("UPDATE jobs SET edit_versions = ? "
                         "WHERE id = ? AND edit_versions = '[]'",
                         (json.dumps(versions), job_id))


_MIGRATIONS: list = [
    _migrate_v1_role,
    _migrate_v2_payment_amounts,
    _migrate_v3_scoped_idempotency,
    _migrate_v4_edit_versions,
]


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist, then apply ordered migrations."""
    conn.executescript(_SCHEMA)
    _apply_migrations(conn)
    _safe_commit(conn)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply ``_MIGRATIONS`` entries above the current ``user_version``.

    Every entry is idempotent, so a database whose version marker is AHEAD
    of the list (possible only from development iterations that renumbered
    entries) is simply re-converged from the start instead of failing.
    """
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    start = current if current <= len(_MIGRATIONS) else 0
    for idx in range(start, len(_MIGRATIONS)):
        entry = _MIGRATIONS[idx]
        # SQLite DDL auto-commits when no transaction is active. Start one
        # explicitly so a failed ALTER and its version marker roll back as a
        # unit; the next startup can retry the migration cleanly.
        conn.execute("BEGIN IMMEDIATE")
        if callable(entry):
            entry(conn)
        else:
            # Migration strings must not use executescript: it commits the
            # active transaction before running its SQL.
            raise TypeError("schema migrations must be callables")
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


# ── Role provisioning (task 04) ─────────────────────────────────

def set_user_role(user_id: str, role: str) -> None:
    """Set the immutable server-side role for a user ('user' or 'admin').

    Only the trusted provisioning CLI may call this — never an HTTP route.
    """
    if role not in ("user", "admin"):
        raise ValueError("role must be 'user' or 'admin'")
    with _write() as conn:
        cur = conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        _safe_commit(conn)
        if cur.rowcount == 0:
            raise ValueError(f"no user with id {user_id!r}")


def get_user_role(user_id: str) -> str:
    """Return the user's role ('user' when unknown)."""
    with _write() as conn:
        row = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    return (row["role"] if row and "role" in row.keys() else None) or "user"


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


# ── Device-link exchange (task 16) ─────────────────────────────────

DEVICE_LINK_TTL_SECONDS = 300  # 5 minutes to complete the handoff


def create_device_link_code(user_id: str, state: str) -> str:
    """Create a one-use, expiring device-link code bound to ``state``.

    Only a verified local session may create one; the code travels to the
    desktop out-of-band (typed or pasted by the owner) and is redeemed
    exactly once.
    """
    import secrets as _secrets
    code = _secrets.token_urlsafe(24)
    now = time.time()
    with _write() as conn:
        conn.execute(
            "INSERT INTO device_link_codes (code, state, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (code, state, user_id, now, now + DEVICE_LINK_TTL_SECONDS),
        )
        _safe_commit(conn)
    return code


def redeem_device_link_code(code: str, state: str) -> str | None:
    """Redeem code+state exactly once; return the user_id or None.

    The UPDATE ... WHERE used_at IS NULL AND expires_at > now is atomic in
    SQLite: a raced duplicate redemption updates zero rows. A wrong state
    never matches (state binding), and expired codes never redeem.
    """
    if not code or not state:
        return None
    with _write() as conn:
        cur = conn.execute(
            "UPDATE device_link_codes SET used_at = ? "
            "WHERE code = ? AND state = ? AND used_at IS NULL AND expires_at > ?",
            (time.time(), code, state, time.time()),
        )
        _safe_commit(conn)
        if cur.rowcount != 1:
            return None
        row = conn.execute(
            "SELECT user_id FROM device_link_codes WHERE code = ?", (code,)
        ).fetchone()
    return row["user_id"] if row else None


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
        # Log the ACTUAL deducted delta (task 08): when the balance was
        # smaller than the requested subtraction, the ledger must reflect
        # what really changed so sum(txn amounts) == balance reconciles.
        _log_txn(conn, user_id, -(current - new_balance), "refund",
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


def job_was_charged(user_id: str, job_id: str) -> bool:
    """Whether this job has its own committed forge debit in the ledger."""
    with _write() as conn:
        row = conn.execute(
            "SELECT 1 FROM credit_transactions WHERE user_id = ? "
            "AND related_id = ? AND type = 'forge' AND amount < 0 LIMIT 1",
            (user_id, job_id),
        ).fetchone()
    return row is not None


def reconcile_ledger() -> dict:
    """Reconcile every credit balance against its transaction sum (task 08).

    For each user the balance must equal the sum of that user's transaction
    amounts — the ledger is the audit authority and every mutation logs the
    ACTUAL delta. Returns {ok, users: [{user_id, balance, ledger_sum, delta}],
    mismatched: n} for scripts/reconcile_ledger.py.
    """
    with _write() as conn:
        balances = {
            r["user_id"]: r["balance"]
            for r in conn.execute("SELECT user_id, balance FROM credits").fetchall()
        }
        sums: dict[str, int] = {}
        for r in conn.execute(
            "SELECT user_id, SUM(amount) AS total FROM credit_transactions "
            "GROUP BY user_id"
        ).fetchall():
            sums[r["user_id"]] = r["total"] or 0

    users = []
    mismatched = 0
    for uid in sorted(set(balances) | set(sums)):
        bal = balances.get(uid, 0)
        total = sums.get(uid, 0)
        ok = bal == total
        if not ok:
            mismatched += 1
        users.append({
            "user_id": uid,
            "balance": bal,
            "ledger_sum": total,
            "delta": bal - total,
            "ok": ok,
        })
    return {"ok": mismatched == 0, "users": users, "mismatched": mismatched}


def has_signup_bonus(user_id: str) -> bool:
    """Check if a user has ever received a signup bonus."""
    with _write() as conn:
        row = conn.execute(
            "SELECT 1 FROM credit_transactions WHERE user_id = ? AND type = 'signup_bonus' LIMIT 1",
            (user_id,),
        ).fetchone()
    return row is not None


def grant_signup_bonus_once(user_id: str, amount: int) -> tuple[bool, int]:
    """Grant the signup bonus at most once — atomic check+grant (task 08).

    The eligibility check (no prior signup_bonus transaction) and the grant
    commit as ONE transaction under the DB write lock, so concurrent calls
    for the same user produce exactly one bonus and one ledger entry.

    Returns (granted_now, new_balance).
    """
    with _write() as conn:
        prior = conn.execute(
            "SELECT 1 FROM credit_transactions WHERE user_id = ? AND type = 'signup_bonus' LIMIT 1",
            (user_id,),
        ).fetchone()
        if prior is not None:
            bal = conn.execute(
                "SELECT balance FROM credits WHERE user_id = ?", (user_id,)
            ).fetchone()
            return False, max(0, bal["balance"]) if bal else 0

        bal = conn.execute(
            "SELECT balance FROM credits WHERE user_id = ?", (user_id,)
        ).fetchone()
        current = max(0, bal["balance"]) if bal else 0
        new_balance = current + amount
        conn.execute(
            "INSERT INTO credits (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance",
            (user_id, new_balance),
        )
        _log_txn(conn, user_id, amount, "signup_bonus",
                 f"Welcome! {amount} free clips.")
        _safe_commit(conn)
    return True, new_balance


def refund_once(user_id: str, amount: int, related_id: str = "",
                reason: str = "") -> tuple[bool, int]:
    """Refund credits at most once per related_id — atomic check+refund (task 08).

    The duplicate-refund guard (existing refund txn for related_id) and the
    refund mutation commit as ONE transaction, so two concurrent refund
    calls for the same job can never both pass the guard.

    Returns (refunded_now, new_balance). refunded_now is False when the
    guard fired (already refunded) or amount <= 0.
    """
    if amount <= 0:
        bal = get_credit_balance(user_id)
        return False, bal

    with _write() as conn:
        if related_id:
            prior = conn.execute(
                "SELECT 1 FROM credit_transactions WHERE related_id = ? "
                "AND type = 'refund' LIMIT 1",
                (related_id,),
            ).fetchone()
            if prior is not None:
                bal = conn.execute(
                    "SELECT balance FROM credits WHERE user_id = ?", (user_id,)
                ).fetchone()
                return False, max(0, bal["balance"]) if bal else 0

        bal = conn.execute(
            "SELECT balance FROM credits WHERE user_id = ?", (user_id,)
        ).fetchone()
        current = max(0, bal["balance"]) if bal else 0
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
    return True, new_balance


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
            "video, clips, timings, edit_versions) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "user_id=excluded.user_id, stage=excluded.stage, progress=excluded.progress, "
            "started_at=excluded.started_at, completed_at=excluded.completed_at, "
            "failed_at=excluded.failed_at, cancelled_at=excluded.cancelled_at, "
            "error=excluded.error, error_code=excluded.error_code, "
            "completed_stages=excluded.completed_stages, "
            "video=excluded.video, clips=excluded.clips, timings=excluded.timings, "
            "edit_versions=excluded.edit_versions",
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
                json.dumps(job.get("edit_versions", [])),
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
            if key in ("completed_stages", "video", "clips", "timings", "edit_versions"):
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
        "edit_versions": json.loads(row["edit_versions"]) if row["edit_versions"] else [],
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


def check_and_charge_idempotent(user_id: str, amount: int, related_id: str = "",
                                key: str = "", operation: str = "forge") -> tuple[bool, int]:
    """Charge credits and persist the replay record — ONE transaction (task 08).

    The charge, its ledger entry and the idempotency result commit together,
    so an injected crash can never produce a charge without a replay record
    or a replay record without a charge. Assumes the replay lookup already
    returned no cached result (see credits.check_and_charge).
    """
    if amount <= 0:
        result = {"success": True, "remaining": get_credit_balance(user_id)}
        if key:
            save_idempotency(key, user_id, operation, result)
        return True, result["remaining"]

    with _write() as conn:
        row = conn.execute("SELECT balance FROM credits WHERE user_id = ?", (user_id,)).fetchone()
        current = max(0, row["balance"]) if row else 0
        if current < amount:
            if key:
                conn.execute(
                    "INSERT OR REPLACE INTO idempotency_keys (key, user_id, operation, result, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (key, user_id, operation, json.dumps({"success": False, "remaining": current}), time.time()),
                )
            _safe_commit(conn)
            return False, current

        new_balance = current - amount
        conn.execute(
            "INSERT INTO credits (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance",
            (user_id, new_balance),
        )
        _log_txn(conn, user_id, -amount, operation,
                 f"Forge clip generation ({amount} credit{'s' if amount != 1 else ''})",
                 related_id=related_id)
        if key:
            conn.execute(
                "INSERT OR REPLACE INTO idempotency_keys (key, user_id, operation, result, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, user_id, operation, json.dumps({"success": True, "remaining": new_balance}), time.time()),
            )
        _safe_commit(conn)
    return True, new_balance


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


def delete_idempotency_for_user(key: str, user_id: str) -> None:
    """Clear only this user's charge replay record after a rejected job."""
    with _write() as conn:
        conn.execute("DELETE FROM idempotency_keys WHERE key = ? AND user_id = ?",
                     (key, user_id))
        _safe_commit(conn)


def cleanup_old_idempotency(active_job_ids: set[str] | None = None) -> int:
    """Remove expired idempotency keys and job mappings. Returns count deleted.

    Task 09: mappings whose job is STILL ACTIVE (job_id in active_job_ids)
    are never evicted, regardless of age — a >24h running job must keep its
    dedupe key so a duplicate submit during the run still replays correctly.
    """
    cutoff = time.time() - 86400
    with _write() as conn:
        c1 = conn.execute("DELETE FROM idempotency_keys WHERE created_at < ?", (cutoff,))
        if active_job_ids:
            # Single statement: delete expired mappings whose job is not active.
            qmarks = ",".join("?" for _ in active_job_ids)
            c2 = conn.execute(
                f"DELETE FROM idempotency_jobs WHERE created_at < ? "
                f"AND job_id NOT IN ({qmarks})",
                (cutoff, *active_job_ids),
            )
        else:
            c2 = conn.execute("DELETE FROM idempotency_jobs WHERE created_at < ?", (cutoff,))
        _safe_commit(conn)
    return c1.rowcount + c2.rowcount


# ── Idempotency → job mapping (one logical submit = one job) ─────────


def get_job_id_for_idempotency(scope: str, key: str) -> str | None:
    """Return the job_id mapped to (scope, key), if any (task 09).

    Scope binds a key to its principal/local-workspace so two users (or a
    user and an anonymous caller) with the same key never dedupe each
    other's work. Pre-migration rows carry scope='' and never match.
    """
    if not key:
        return None
    with _write() as conn:
        row = conn.execute(
            "SELECT job_id FROM idempotency_jobs WHERE scope = ? AND key = ?",
            (scope, key),
        ).fetchone()
    return row["job_id"] if row else None


def get_idempotency_fingerprint(scope: str, key: str) -> str | None:
    """Return the stored request fingerprint for (scope, key), if any."""
    if not key:
        return None
    with _write() as conn:
        row = conn.execute(
            "SELECT fingerprint FROM idempotency_jobs WHERE scope = ? AND key = ?",
            (scope, key),
        ).fetchone()
    return row["fingerprint"] if row else None


def save_idempotency_job(key: str, job_id: str, user_id: str | None,
                         scope: str = "", fingerprint: str = "") -> None:
    """Atomically record that (scope, key) maps to a created job.

    fingerprint is the canonical request fingerprint (task 09): a later
    replay with the same scoped key but a different fingerprint is a
    conflict (409), not a silent stale replay.
    """
    with _write() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO idempotency_jobs (key, job_id, user_id, created_at, scope, fingerprint) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (key, job_id, user_id, time.time(), scope, fingerprint),
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

    # Job snapshots are imported by the versioned v4 migration only.
    # Repeating that import on every startup could recreate a deleted job.


def backup_database(dest_dir: str | Path | None = None) -> Path | None:
    """Create a versioned, SQLite-safe backup (task 10).

    ``VACUUM INTO`` produces a consistent snapshot even while writers are
    active. Each backup gets a timestamped filename in ``<data>/backups/``
    (or dest_dir), so repeated backups never collide on the destination —
    the F11 defect where the second backup failed because the fixed
    ``.db.bak`` path already existed.

    The destination path is passed to SQLite as a bound parameter via a
    parameterized ``VACUUM INTO``-equivalent: SQLite does not support bound
    parameters in VACUUM INTO, so the path is quoted with SQL string
    escaping (doubled single-quotes) — paths containing apostrophes/spaces
    are handled correctly.

    Returns the backup path, or None when there is no database yet.
    """
    if not _DB_PATH.exists():
        return None
    import secrets as _secrets
    base = Path(dest_dir) if dest_dir else _DB_PATH.parent / "backups"
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = base / f"clpz-{stamp}-{_secrets.token_hex(3)}.db"
    # Deterministic unique name even under same-second calls.
    n = 0
    while backup.exists():
        n += 1
        backup = base / f"clpz-{stamp}-{_secrets.token_hex(3)}-{n}.db"
    escaped = str(backup).replace("'", "''")
    with _write() as conn:
        conn.execute(f"VACUUM INTO '{escaped}'")
    return backup


def backup_schema_version(db_path: str | Path) -> int:
    """Read the schema version of a database file WITHOUT migrating it.

    Used by restore validation (task 10): a backup must be schema-compatible
    with the running application before it is activated.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def validate_backup(db_path: str | Path) -> dict:
    """Validate a backup file before restore (task 10).

    Checks file integrity (SQLite quick_check) and schema compatibility
    against the running application's migration list.
    """
    report: dict = {"path": str(db_path), "exists": Path(db_path).exists(),
                    "integrity": None, "schema_version": None,
                    "compatible": False, "error": ""}
    if not report["exists"]:
        report["error"] = "Backup file does not exist."
        return report
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            report["integrity"] = conn.execute("PRAGMA quick_check").fetchone()[0]
            report["schema_version"] = int(
                conn.execute("PRAGMA user_version").fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error as e:
        report["error"] = f"Cannot open backup: {e}"
        return report
    if report["integrity"] != "ok":
        report["error"] = f"Integrity check failed: {report['integrity']}"
        return report
    # Compatible when the backup's schema is not newer than this app can read.
    report["compatible"] = report["schema_version"] <= len(_MIGRATIONS)
    if not report["compatible"]:
        report["error"] = (
            f"Backup schema v{report['schema_version']} is newer than this "
            f"application supports (v{len(_MIGRATIONS)})."
        )
    return report


def restore_database(backup_path: str | Path, target_dir: str | Path | None = None,
                     *, validate: bool = True) -> dict:
    """Restore a backup into a NEW directory — never over the live database
    (task 10 acceptance: 'restore to a separate directory', 'never overwrite
    the only working copy').

    Workflow: validate → copy the backup into ``target_dir`` (default:
    ``<data>/restored-<stamp>/``) as ``clpz.db`` → open, checkpoint WAL and
    re-validate → report. The caller decides when to switch CLIPFORGE_DATA
    to the restored directory; the live store is never mutated in place.
    """
    import shutil as _shutil
    src = Path(backup_path)
    if validate:
        report = validate_backup(src)
        if not report["compatible"] or report["integrity"] != "ok":
            return {"ok": False, "error": report["error"] or "backup failed validation",
                    "validation": report}
    if not src.exists():
        return {"ok": False, "error": f"backup not found: {src}"}

    if target_dir is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target_dir = _DB_PATH.parent / f"restored-{stamp}"
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / "clpz.db"

    _shutil.copy2(src, dest)
    conn = sqlite3.connect(str(dest))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()

    ok = integrity == "ok" and version <= len(_MIGRATIONS)
    return {
        "ok": ok,
        "restored_path": str(dest),
        "integrity": integrity,
        "schema_version": version,
        "next_step": (
            "Point CLIPFORGE_DATA at this directory (or replace the live "
            "clpz.db after stopping the app) after reviewing projects."
            if ok else "Backup failed post-restore validation; keep the live data."
        ),
    }


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
                   raw_json: str = "", credits_granted: int | None = None) -> tuple[bool, str]:
    """Record an external payment exactly once.

    Returns (created, payment_id). If a payment with the same
    (provider, external_id) already exists, returns (False, existing_id)
    and does NOT modify anything — this is the idempotency guard that
    prevents duplicate webhooks from granting credits twice.

    user_id may be None for purchases that could not be linked to a CLPZ
    account (audit trail only, no FK enforced).

    credits_granted records the number of credits the caller INTENDS to
    grant for this payment (task 08). Persisting the intended amount means
    a later reversal reverses what was actually granted instead of
    re-deriving it from current configuration. NULL means "not yet
    fulfilled" — use fulfill_payment_credits() to record the grant and the
    credit mutation in ONE transaction.
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
            "amount_cents, currency, status, raw_json, created_at, credits_granted) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (payment_id, user_id, provider, external_id, product_id,
             amount_cents, currency, status, raw_json, time.time(), credits_granted),
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


# ── Atomic payment fulfillment (task 08) ──────────────────────────


def fulfill_payment_credits(provider: str, external_id: str, user_id: str,
                            amount: int, txn_type: str = "purchase",
                            description: str = "") -> tuple[bool, int]:
    """Grant credits for a recorded payment and mark it fulfilled — ONE transaction.

    The payment row must already exist (record_payment). The grant is applied
    and credits_granted is set in the same commit, so a crash between the two
    is impossible and a replay can detect completion via credits_granted.

    Returns (fulfilled_now, new_balance). fulfilled_now is False when the
    payment was already fulfilled (credits_granted NOT NULL) — a duplicate
    webhook replay then grants nothing again.
    """
    if amount <= 0:
        # Nothing to grant; still mark fulfillment complete so replays are no-ops.
        with _write() as conn:
            conn.execute(
                "UPDATE payments SET credits_granted = 0 "
                "WHERE provider = ? AND external_id = ? AND credits_granted IS NULL",
                (provider, external_id),
            )
            _safe_commit(conn)
        return False, get_credit_balance(user_id)

    with _write() as conn:
        row = conn.execute(
            "SELECT credits_granted FROM payments WHERE provider = ? AND external_id = ?",
            (provider, external_id),
        ).fetchone()
        if row is None:
            raise ValueError(f"payment {provider}/{external_id} not recorded")
        if row["credits_granted"] is not None:
            # Already fulfilled — replay is a no-op.
            bal = conn.execute(
                "SELECT balance FROM credits WHERE user_id = ?", (user_id,)
            ).fetchone()
            return False, max(0, bal["balance"]) if bal else 0

        bal = conn.execute(
            "SELECT balance FROM credits WHERE user_id = ?", (user_id,)
        ).fetchone()
        current = max(0, bal["balance"]) if bal else 0
        new_balance = current + amount
        conn.execute(
            "INSERT INTO credits (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance",
            (user_id, new_balance),
        )
        _log_txn(conn, user_id, amount, txn_type, description, related_id=external_id)
        conn.execute(
            "UPDATE payments SET credits_granted = ? WHERE provider = ? AND external_id = ?",
            (amount, provider, external_id),
        )
        _safe_commit(conn)
    return True, new_balance


def reverse_payment_credits(provider: str, external_id: str, user_id: str,
                            fallback_amount: int | None = None,
                            reason: str = "") -> tuple[bool, int]:
    """Reverse a payment's credit grant exactly once — ONE transaction.

    Reverses credits_granted when known; otherwise falls back to
    fallback_amount (legacy rows whose original amount was never recorded).
    Marks credits_reversed in the same commit, so a duplicate refund
    webhook can never reverse twice (it sees credits_reversed already set).

    Returns (reversed_now, new_balance). reversed_now is False when nothing
    was reversed now (already reversed, nothing granted, or no known amount).
    """
    with _write() as conn:
        row = conn.execute(
            "SELECT user_id, credits_granted, credits_reversed FROM payments "
            "WHERE provider = ? AND external_id = ?",
            (provider, external_id),
        ).fetchone()
        if row is None:
            raise ValueError(f"payment {provider}/{external_id} not recorded")
        if row["user_id"] and row["user_id"] != user_id:
            raise ValueError(
                f"payment {provider}/{external_id} belongs to a different user"
            )
        if row["credits_reversed"]:
            bal = conn.execute(
                "SELECT balance FROM credits WHERE user_id = ?", (user_id,)
            ).fetchone()
            return False, max(0, bal["balance"]) if bal else 0

        amount = row["credits_granted"] if row["credits_granted"] is not None else fallback_amount
        if amount is None or amount <= 0:
            # Nothing known to reverse (or nothing was ever granted). Every
            # replay takes this same no-op path, so duplicates stay safe.
            bal = conn.execute(
                "SELECT balance FROM credits WHERE user_id = ?", (user_id,)
            ).fetchone()
            return False, max(0, bal["balance"]) if bal else 0

        bal = conn.execute(
            "SELECT balance FROM credits WHERE user_id = ?", (user_id,)
        ).fetchone()
        current = max(0, bal["balance"]) if bal else 0
        new_balance = max(0, current - amount)
        conn.execute(
            "INSERT INTO credits (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance",
            (user_id, new_balance),
        )
        _log_txn(conn, user_id, -(current - new_balance), "refund",
                 reason or f"Payment reversal {external_id}", related_id=external_id)
        conn.execute(
            "UPDATE payments SET credits_reversed = ? WHERE provider = ? AND external_id = ?",
            (current - new_balance, provider, external_id),
        )
        _safe_commit(conn)
    return True, new_balance
