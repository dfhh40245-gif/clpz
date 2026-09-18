"""Windows cloud account handoff, separate from local SQLite identity/credits.

The website verifies Supabase Auth and issues a one-use code. The desktop
exchanges code plus its private state directly with that website. A returned
opaque device credential is encrypted for the current Windows account using
DPAPI; it is never treated as a local credit or entitlement grant.
"""
from __future__ import annotations

import ctypes
import os
import re
import secrets
import sys
import threading
import time
import uuid
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlparse

import requests

import config

_pending: tuple[str, float] | None = None
_lock = threading.Lock()
_STORE_NAME = "cloud-device.dat"


class CloudIdentityError(RuntimeError):
    pass


class CloudSessionMissing(CloudIdentityError):
    """The device has no usable linked account credential."""


def _site_origin() -> str:
    configured = os.getenv("CLPZ_ACCOUNT_URL", "").rstrip("/")
    parsed = urlparse(configured)
    if (not parsed.netloc or parsed.username or parsed.password or parsed.path or
            parsed.query or parsed.fragment or parsed.scheme not in ("https", "http") or
            (parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"))):
        raise CloudIdentityError("Cloud account website is not configured securely.")
    return configured


def _store_path() -> Path:
    return config.DATA_DIR / _STORE_NAME


def _dpapi(data: bytes, *, protect: bool) -> bytes:
    if sys.platform != "win32":
        raise CloudIdentityError("Secure cloud credential storage requires Windows.")

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    source_buffer = ctypes.create_string_buffer(data)
    source = DATA_BLOB(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    result = DATA_BLOB()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    func = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    func.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
                     ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                     ctypes.POINTER(DATA_BLOB)]
    func.restype = wintypes.BOOL
    if not func(ctypes.byref(source), None, None, None, None, 0x1, ctypes.byref(result)):
        raise CloudIdentityError("Could not protect the cloud credential.")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        kernel32.LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))


def _save_token(token: str) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = _dpapi(token.encode("ascii"), protect=True)
    staged = path.with_suffix(".tmp")
    staged.write_bytes(encrypted)
    os.replace(staged, path)


def _load_token() -> str | None:
    path = _store_path()
    if not path.exists():
        return None
    try:
        token = _dpapi(path.read_bytes(), protect=False).decode("ascii")
    except (OSError, UnicodeError, CloudIdentityError):
        raise CloudIdentityError("Saved cloud sign-in cannot be read; please sign in again.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        raise CloudIdentityError("Saved cloud sign-in is invalid; please sign in again.")
    return token


def begin_link() -> dict:
    global _pending
    origin = _site_origin()
    if _load_token():
        raise CloudIdentityError("Disconnect the current cloud account before linking another.")
    state = secrets.token_urlsafe(32)
    with _lock:
        _pending = (state, time.monotonic() + 300)
    return {"state": state, "website_url": origin + "/account", "expires_in": 300}


def complete_link(code: str) -> dict:
    global _pending
    origin = _site_origin()
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", code):
        raise CloudIdentityError("Invalid device link code.")
    with _lock:
        pending = _pending
        _pending = None  # one local attempt; begin again after failure
    if not pending or pending[1] <= time.monotonic():
        raise CloudIdentityError("Start a fresh device link first.")
    try:
        response = requests.post(
            origin + "/api/cloud/device-link/redeem",
            json={"code": code, "state": pending[0]}, timeout=10,
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise CloudIdentityError("Device link code was rejected or cloud service is unavailable.")
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CloudIdentityError("Cloud account service is unavailable.") from exc
    token = body.get("token")
    user_id = body.get("user_id")
    if (body.get("issuer") != origin or body.get("audience") != "clpz-desktop" or
            not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token) or
            not isinstance(user_id, str)):
        raise CloudIdentityError("Cloud identity response failed validation.")
    try:
        uuid.UUID(user_id)
    except ValueError as exc:
        raise CloudIdentityError("Cloud identity response failed validation.") from exc
    _save_token(token)
    return {"linked": True, "user_id": user_id}


def account() -> dict:
    token = _load_token()
    if not token:
        raise CloudSessionMissing("No cloud account is linked.")
    try:
        response = requests.get(
            _site_origin() + "/api/cloud/device",
            headers={"Authorization": "Bearer " + token}, timeout=10,
            allow_redirects=False,
        )
        if response.status_code == 401:
            raise CloudSessionMissing("Cloud sign-in expired or was revoked; link again.")
        if response.status_code != 200:
            raise CloudIdentityError("Cloud account service is unavailable.")
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CloudIdentityError("Cloud account service is unavailable.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("credits"), int) or not isinstance(data.get("entitlements"), list):
        raise CloudIdentityError("Cloud account response is invalid.")
    return data


def unlink() -> None:
    token = _load_token()
    if not token:
        return
    try:
        response = requests.delete(
            _site_origin() + "/api/cloud/device",
            headers={"Authorization": "Bearer " + token}, timeout=10,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise CloudIdentityError("Cloud service is unavailable; sign-out was not completed.") from exc
    if response.status_code not in (200, 401):
        raise CloudIdentityError("Cloud sign-out could not be confirmed.")
    _store_path().unlink(missing_ok=True)
