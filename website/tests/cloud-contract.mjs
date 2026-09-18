import assert from "node:assert/strict";
import { test } from "node:test";
import { digest, newSecret, validSecret, sameOriginPost } from "../lib/cloud-device.ts";
import { readCloudAccount } from "../lib/cloud-account.ts";

test("device code/state use independent high-entropy values and fixed digests", () => {
  const code = newSecret(), state = newSecret();
  assert.ok(validSecret(code) && validSecret(state));
  assert.notEqual(code, state);
  assert.equal(digest(code).length, 64);
  assert.notEqual(digest(code), digest(state));
  assert.equal(validSecret("short"), false);
});

test("browser mint rejects a cross-origin POST", () => {
  const good = new Request("https://site.example/api/cloud/device-link", {
    method: "POST", headers: { origin: "https://site.example" },
  });
  const bad = new Request("https://site.example/api/cloud/device-link", {
    method: "POST", headers: { origin: "https://attacker.example" },
  });
  assert.equal(sameOriginPost(good), true);
  assert.equal(sameOriginPost(bad), false);
});

function fakeCloudDb(rows, fail = false) {
  return { from(table) {
    let owner;
    const query = {
      select() { return query; }, eq(column, value) { assert.equal(column, "user_id"); owner = value; return query; },
      order() { return query; }, limit() { return Promise.resolve({ data: rows[table].filter(row => row.user_id === owner), error: fail ? { code: "down" } : null }); },
      maybeSingle() { return Promise.resolve({ data: rows[table].find(row => row.user_id === owner) ?? null, error: fail ? { code: "down" } : null }); },
      then(resolve) { return Promise.resolve({ data: rows[table].filter(row => row.user_id === owner), error: fail ? { code: "down" } : null }).then(resolve); },
    };
    return query;
  } };
}

test("cloud account reads only the authenticated user's current rows", async () => {
  const rows = {
    credit_accounts: [{ user_id: "A", balance: 7 }, { user_id: "B", balance: 900 }],
    subscriptions: [{ user_id: "A", plan: "creator", status: "active" }, { user_id: "B", plan: "other", status: "active" }],
    entitlements: [{ user_id: "A", feature: "creator", expires_at: null },
      { user_id: "A", feature: "expired", expires_at: "2020-01-01T00:00:00Z" },
      { user_id: "B", feature: "other", expires_at: null }],
  };
  const a = await readCloudAccount(fakeCloudDb(rows), "A");
  assert.equal(a.credits, 7);
  assert.deepEqual(a.entitlements.map(item => item.feature), ["creator"]);
  assert.equal(a.subscription.plan, "creator");
  await assert.rejects(readCloudAccount(fakeCloudDb(rows, true), "A"), /unavailable/);
});
