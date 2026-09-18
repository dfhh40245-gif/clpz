"""R08 local contract: cloud handoff, online account view, secure storage."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cloud_identity as cloud  # noqa: E402
from tests.test_remediation import isolated_data  # noqa: F401,E402


@pytest.fixture(autouse=True)
def configured_site(monkeypatch):
    monkeypatch.setenv("CLPZ_ACCOUNT_URL", "http://127.0.0.1:3000")
    cloud._pending = None
    yield
    cloud._pending = None


def _response(status: int, body: dict):
    return Mock(status_code=status, json=lambda: body)


def test_one_use_handoff_verifies_issuer_audience_and_persists_encrypted_token(
    isolated_data, monkeypatch,
):
    started = cloud.begin_link()
    assert started["website_url"] == "http://127.0.0.1:3000/account"
    assert len(started["state"]) >= 32
    code = "c" * 43
    user_id = str(uuid.uuid4())
    token = "t" * 43
    calls = []

    def website_post(url, *, json, timeout, allow_redirects):
        calls.append((url, json, timeout, allow_redirects))
        return _response(200, {
            "token": token, "user_id": user_id,
            "issuer": "http://127.0.0.1:3000", "audience": "clpz-desktop",
        })

    monkeypatch.setattr(cloud.requests, "post", website_post)
    linked = cloud.complete_link(code)
    assert linked == {"linked": True, "user_id": user_id}
    assert calls == [("http://127.0.0.1:3000/api/cloud/device-link/redeem",
                      {"code": code, "state": started["state"]}, 10, False)]
    saved = isolated_data / "cloud-device.dat"
    assert saved.exists()
    assert token.encode() not in saved.read_bytes()
    assert cloud._load_token() == token  # works after module state is cleared/restart
    assert cloud._pending is None
    with pytest.raises(cloud.CloudIdentityError, match="Start a fresh"):
        cloud.complete_link(code)


@pytest.mark.parametrize("override", [
    {"issuer": "https://impostor.example"},
    {"audience": "another-app"},
    {"user_id": "local-sqlite-id"},
])
def test_invalid_cloud_identity_response_never_links(isolated_data, monkeypatch, override):
    cloud.begin_link()
    body = {
        "token": "t" * 43, "user_id": str(uuid.uuid4()),
        "issuer": "http://127.0.0.1:3000", "audience": "clpz-desktop",
    } | override
    monkeypatch.setattr(cloud.requests, "post", lambda *args, **kwargs: _response(200, body))
    with pytest.raises(cloud.CloudIdentityError, match="failed validation"):
        cloud.complete_link("c" * 43)
    assert not (isolated_data / "cloud-device.dat").exists()


def test_cloud_account_is_live_and_signout_revokes_device(isolated_data, monkeypatch):
    cloud._save_token("t" * 43)
    with pytest.raises(cloud.CloudIdentityError, match="Disconnect"):
        cloud.begin_link()
    user_id = str(uuid.uuid4())
    cloud_snapshot = {"user_id": user_id, "credits": 4,
                      "subscription": None, "entitlements": [{"feature": "creator"}]}
    requests_seen = []
    def website_get(url, *, headers, timeout, allow_redirects):
        requests_seen.append((url, headers, allow_redirects))
        return _response(200, cloud_snapshot)
    monkeypatch.setattr(cloud.requests, "get", website_get)
    assert cloud.account()["credits"] == 4
    cloud_snapshot["credits"] = 2
    assert cloud.account()["credits"] == 2  # no cached/local balance
    assert all(item[0].endswith("/api/cloud/device") and
               item[1] == {"Authorization": "Bearer " + "t" * 43} and
               item[2] is False for item in requests_seen)

    monkeypatch.setattr(cloud.requests, "delete", lambda *args, **kwargs: _response(200, {"ok": True}))
    cloud.unlink()
    assert not (isolated_data / "cloud-device.dat").exists()
    with pytest.raises(cloud.CloudIdentityError, match="No cloud account"):
        cloud.account()


def test_site_origin_and_remote_signout_fail_closed(isolated_data, monkeypatch):
    monkeypatch.setenv("CLPZ_ACCOUNT_URL", "http://public.example")
    with pytest.raises(cloud.CloudIdentityError, match="not configured securely"):
        cloud.begin_link()
    monkeypatch.setenv("CLPZ_ACCOUNT_URL", "http://127.0.0.1:3000")
    cloud._save_token("t" * 43)
    monkeypatch.setattr(cloud.requests, "delete", lambda *args, **kwargs: _response(503, {}))
    with pytest.raises(cloud.CloudIdentityError, match="could not be confirmed"):
        cloud.unlink()
    assert cloud._load_token() == "t" * 43


def test_cloud_http_routes_keep_local_identity_separate(isolated_data, monkeypatch):
    from fastapi.testclient import TestClient
    import main
    token = main._capability.new_token()
    monkeypatch.setattr(cloud, "begin_link", lambda: {"state": "s" * 43, "website_url": "http://127.0.0.1:3000/account", "expires_in": 300})
    monkeypatch.setattr(cloud, "complete_link", lambda code: {"linked": True, "user_id": str(uuid.uuid4())})
    monkeypatch.setattr(cloud, "account", lambda: {"user_id": str(uuid.uuid4()), "credits": 0, "entitlements": [], "subscription": None})
    client = TestClient(main.app, base_url="http://127.0.0.1:8000")
    assert client.post("/api/cloud/link/start").status_code == 403
    headers = {"X-CLPZ-Capability": token}
    assert client.post("/api/cloud/link/start", headers=headers).status_code == 200
    assert client.post("/api/cloud/link/complete", json={"code": "c" * 43}, headers=headers).status_code == 200
    assert client.get("/api/cloud/account").json()["credits"] == 0
    # No local clpz_session was minted by the cloud exchange.
    assert "clpz_session" not in client.cookies
    def not_linked():
        raise cloud.CloudSessionMissing("No cloud account is linked.")
    monkeypatch.setattr(cloud, "account", not_linked)
    assert client.get("/api/cloud/account").status_code == 401
