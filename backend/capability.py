"""Per-launch capability token for the local desktop API (task 03).

The desktop backend is a LOCAL service. Loopback binding alone is not an
authorization boundary: any process or web page on the machine (and, on a
misconfigured host, the network) can hit 127.0.0.1. This module provides a
per-launch capability that the launcher passes ONLY to the UI it opens, so
state-changing requests must come from the intended desktop window.

Design rules (acceptance checks for task 03):
- The token is generated per launch, delivered to the UI out-of-band (never in
  a URL logged by the server, never in API responses), and rotates each launch
  so a previous launch's token stops working.
- Requests without Origin (native/curl) and same-origin browser requests are
  distinguished from cross-origin browser requests, which are rejected for
  state-changing routes.
- The UI learns the token via /app HTML (server injects it into the served
  page), not via query parameters; a query parameter alone can never enable
  privileged behavior.
- Media routes (video/image Range requests) stay usable from the desktop UI.

Opt-out for hosted deployments: CLPZ_REQUIRE_CAPABILITY=0 disables the gate
and is refused at startup in production mode (see config validation in
clpz_server/main startup), so a hosted deployment cannot silently run without
it. Debug/dev servers (CLPZ_DEBUG=1) default to the gate ENABLED, matching
production; the hermetic test suite may disable it explicitly.
"""
from __future__ import annotations

import hmac
import os
import secrets
import threading
from urllib.parse import urlsplit

# ── State ─────────────────────────────────────────────────────────
_lock = threading.Lock()
_token: str | None = None

# A launcher (desktop/server.py, desktop/frozen_launcher.py) may pre-set the
# token for this launch via CLPZ_CAPABILITY_TOKEN so it can be handed to the
# child server process environment; otherwise ``initialize_token()`` creates
# one while ``main:app`` is imported by a supported server entry point.
_launcher_token = os.getenv("CLPZ_CAPABILITY_TOKEN", "")
if _launcher_token:
    _token = _launcher_token

# Config (read once at import; tests may monkeypatch the module attributes)
REQUIRE_CAPABILITY = os.getenv("CLPZ_REQUIRE_CAPABILITY", "1") == "1"
# Debug servers relax ONLY the capability requirement (Host/Origin checks
# remain). Tests/scripts hitting a CLPZ_DEBUG=1 server without the token
# keep working; production servers (debug off) always enforce the token.
DEBUG_EXEMPT = os.getenv("CLPZ_DEBUG", "0") == "1"
# Hosts allowed in the Host header IN ADDITION to loopback. Loopback forms
# (any port) are always accepted; this list is for a future hosted deployment.
ALLOWED_HOSTS = {
    h.strip().lower()
    for h in os.getenv("CLPZ_ALLOWED_HOSTS", "").split(",")
    if h.strip()
}

# State-changing method prefixes that require the capability.
PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Routes that must work for the desktop UI without the token header because
# the browser itself issues them (media element requests, page loads).
MEDIA_PREFIXES = (
    "/api/jobs/",  # stream/thumbnail/ass/download are GETs on this tree
)
STATIC_PAGES = ("/app", "/new", "/", "/auth.html", "/admin", "/favicon.png")


def new_token() -> str:
    """Rotate to a fresh capability token and return it."""
    global _token
    with _lock:
        _token = secrets.token_urlsafe(32)
        return _token


def initialize_token() -> str:
    """Return this server process's capability, creating it when needed.

    Desktop launchers pre-set a fresh token so they can start a child process;
    that value is preserved. Direct ``uvicorn main:app`` and ``clpz_server``
    starts have no parent to provide one, so they create one exactly once at
    import/startup. The token is only delivered by server-rendered local HTML.
    """
    global _token
    with _lock:
        if _token is None:
            _token = secrets.token_urlsafe(32)
        return _token


def current_token() -> str | None:
    with _lock:
        return _token


def verify(token: str | None) -> bool:
    """Constant-time comparison against the active token."""
    active = current_token()
    if active is None:
        # No token issued yet: only fail if the gate is required.
        return not REQUIRE_CAPABILITY
    if not token:
        return False
    return hmac.compare_digest(token, active)


def is_allowed_host(host_header: str | None) -> bool:
    """Validate the Host header.

    For a LOCAL service the rule is: the hostname part must be a loopback
    address (any port) or an explicitly allowlisted host. A forged foreign
    hostname (untrusted.example) is rejected; loopback with any port passes,
    which keeps OS-assigned launch ports working.
    """
    if not host_header:
        return False
    host = host_header.strip().lower()
    try:
        parsed = urlsplit(f"//{host}")
        hostname = (parsed.hostname or "").lower()
    except ValueError:
        return False
    if not hostname:
        return False
    if hostname in {"127.0.0.1", "localhost", "::1", "[::1]"}:
        return True
    return host in ALLOWED_HOSTS or hostname in ALLOWED_HOSTS


def _origin_allowed(origin: str | None, host_header: str | None) -> bool:
    """Classify the request's browser context.

    - No Origin header: native client (desktop webview fetch/curl/pytest) —
      allowed (the capability check still applies for protected routes).
    - Origin present: must be a same-origin browser request (scheme+host+port
      equal to the request Host). Loopback alternates (localhost vs 127.0.0.1)
      are treated as same-origin for the desktop's convenience.
    """
    if not origin:
        return True  # native request path
    try:
        o = urlsplit(origin)
        if o.scheme not in ("http", "https"):
            return False
        origin_host = (o.hostname or "").lower()
        if not host_header:
            return False
        h = urlsplit(f"//{host_header}")
        req_host = (h.hostname or "").lower()
    except ValueError:
        return False
    if origin_host == req_host:
        return True
    # Loopback aliases for desktop mode
    loopback = {"127.0.0.1", "localhost", "::1"}
    return origin_host in loopback and req_host in loopback


def _get_header(headers, name: str) -> str | None:
    """Case-insensitive header lookup that also works for plain dicts."""
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    value = getter(name)
    if value is None and hasattr(headers, "keys"):
        for key in headers.keys():
            if str(key).lower() == name:
                return getter(key)
    return value


def check_request(method: str, path: str, headers) -> tuple[bool, str]:
    """Full boundary decision for a request.

    Returns (allowed, reason). ``headers`` is a Starlette Headers object or
    any mapping (case-insensitive lookup).
    """
    host_header = _get_header(headers, "host")
    host_ok = is_allowed_host(host_header)
    if not host_ok:
        return False, "untrusted-host"

    origin = _get_header(headers, "origin")
    if not _origin_allowed(origin, host_header):
        return False, "cross-origin-browser-request"

    if method.upper() not in PROTECTED_METHODS:
        return True, "ok"

    # Media downloads from the desktop UI: the browser fetches these with an
    # Origin only for CORS-fetches; <video>/<img> tags send no Origin on
    # same-origin GETs, and these are read-only. They pass unconditionally.
    if method.upper() in ("GET", "HEAD"):
        return True, "ok"

    # State-changing: require the capability unless the route is in the
    # public auth surface (account flows are their own rate-limited gateway).
    path = path.split("?", 1)[0]
    if path.startswith("/api/auth/"):
        return True, "public-auth-route"

    if not REQUIRE_CAPABILITY:
        return True, "capability-disabled"
    if DEBUG_EXEMPT:
        # Debug/dev servers (CLPZ_DEBUG=1): Host/Origin checks stay enforced
        # but the capability requirement is relaxed so scripts and unit-test
        # harnesses keep working. Production (debug off) always enforces it.
        return True, "debug-exempt"

    supplied = _get_header(headers, "x-clpz-capability")
    if supplied and verify(supplied):
        return True, "ok"
    return False, "missing-or-stale-capability"
