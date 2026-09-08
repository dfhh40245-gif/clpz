/**
 * Regression tests for the vanilla CLPZ workspace (frontend/clpz.html).
 *
 * These target previously-confirmed functional bugs:
 *  - "Change File" button used a broken selector (`$('file')`) and never
 *    triggered the file input.
 *  - The Settings page read `d.opencut` while the API returns
 *    `{"editor": "built-in"}`, so the Editor row always showed "Unavailable".
 *  - Forge submissions must carry a stable idempotency key so one logical
 *    submission can never create two jobs / double-charge.
 */
import { describe, it, expect } from "vitest";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const htmlPath = resolve(process.cwd(), "../frontend/clpz.html");
const html = readFileSync(htmlPath, "utf-8");

function makeDom() {
  const dom = new JSDOM(html, {
    runScripts: "dangerously",
    url: "http://127.0.0.1:8000/app?desktop=1",
    pretendToBeVisual: true,
    beforeParse(window) {
      window.scrollTo = () => {};
      Object.defineProperty(window, "crypto", {
        configurable: true,
        value: { randomUUID: () => "idem-00000000-1111-2222-3333-444444444444" },
      });
      window.fetch = async (url) => {
        const u = String(url);
        if (u.includes("/api/diagnostics")) {
          return {
            ok: true, status: 200,
            headers: { get: () => "application/json" },
            json: async () => ({
              ffmpeg: "found", ffprobe: "found", "yt-dlp": "found",
              whisper: "v3", ram: "8 GB", disk: "50 GB",
              cpu_count: 8, editor: "built-in",
            }),
          };
        }
        // Everything else: pretend there are no jobs / no session.
        return {
          ok: true, status: 200,
          headers: { get: () => "application/json" },
          json: async () => [],
        };
      };
    },
  });
  return dom;
}

describe("CLPZ vanilla workspace (functional regressions)", () => {
  it("Change File button triggers the real file input", () => {
    const dom = makeDom();
    const { window } = dom;
    const input = window.document.getElementById("file");
    expect(input).toBeTruthy();
    let inputClicked = 0;
    input.addEventListener("click", () => { inputClicked += 1; });
    const changeBtn = window.document.getElementById("change-file");
    expect(changeBtn).toBeTruthy();
    changeBtn.click();
    expect(inputClicked).toBe(1);
    dom.window.close();
  });

  it("Settings Editor row renders the API value (editor: built-in)", async () => {
    const dom = makeDom();
    const { window } = dom;
    const diag = window.document.getElementById("diagnostics");
    expect(diag).toBeTruthy();
    await window.eval("loadDiagnostics()");
    // Give the async api() call a chance to resolve.
    await new Promise((r) => setTimeout(r, 100));
    const htmlOut = diag.innerHTML;
    expect(htmlOut).toContain("built-in");
    expect(htmlOut).not.toContain("opencut");
    dom.window.close();
  });

  it("forge URL submission includes a stable idempotency key", async () => {
    const dom = makeDom();
    const { window } = dom;
    const calls = [];
    window.fetch = async (url, opts = {}) => {
      calls.push({ url: String(url), body: opts.body });
      if (String(url).includes("/api/jobs")) {
        return {
          ok: true, status: 200,
          headers: { get: () => "application/json" },
          json: async () => ({ job_id: "abc123", credits_remaining: 9 }),
        };
      }
      return {
        ok: true, status: 200,
        headers: { get: () => "application/json" },
        json: async () => [],
      };
    };
    window.document.getElementById("url").value = "https://www.youtube.com/watch?v=xyz";
    await window.eval("forgeUrl()");
    const forgeCall = calls.find((c) => String(c.url).endsWith("/api/jobs"));
    expect(forgeCall).toBeTruthy();
    const body = JSON.parse(forgeCall.body);
    expect(body.idempotency_key).toBe("idem-00000000-1111-2222-3333-444444444444");
    dom.window.close();
  });
});