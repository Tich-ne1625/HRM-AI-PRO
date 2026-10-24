// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ApiClientError, resetApiSession } from "./api-client";

const ok = (value: unknown = { ok: true }) =>
  new Response(JSON.stringify(value), { status: 200 });
const unauthorized = () => new Response(JSON.stringify({
  error: { code: "authentication_required", message: "Authentication required", details: [] },
}), { status: 401 });

describe("cookie API client", () => {
  beforeEach(() => { resetApiSession(); document.cookie = "insighthr_csrf=family-proof; path=/"; });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("includes cookies and attaches CSRF only to mutations", async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(ok()));
    vi.stubGlobal("fetch", fetcher);
    await apiFetch("/api/v1/users");
    await apiFetch("/api/v1/users", { method: "POST", body: "{}" });
    const read = fetcher.mock.calls[0]?.[1] as RequestInit;
    const write = fetcher.mock.calls[1]?.[1] as RequestInit;
    expect(read.credentials).toBe("include");
    expect(new Headers(read.headers).has("X-CSRF-Token")).toBe(false);
    expect(new Headers(write.headers).get("X-CSRF-Token")).toBe("family-proof");
    expect(new Headers(write.headers).get("Content-Type")).toBe("application/json");
  });

  it("parses stable API errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: "last_active_admin", message: "Protected administrator", details: [] },
    }), { status: 409 })));
    await expect(apiFetch("/api/v1/users")).rejects.toMatchObject({
      status: 409, code: "last_active_admin", message: "Protected administrator",
    });
  });

  it("retains structured validation issues and discards invalid detail entries", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: {code: "activation_requirements_not_met", message: "Requirements", details: [
        {employee_id: "employee", code: "self_account_required"}, null, "invalid", [],
      ]},
    }), {status: 409})));
    await expect(apiFetch("/api/v1/review-cycles/cycle/activate", {method: "POST", body: "{}"})).rejects.toMatchObject({
      status: 409, details: [{employee_id: "employee", code: "self_account_required"}],
    });
  });

  it("shares one refresh among ten simultaneous 401 responses and retries each once", async () => {
    let reads = 0;
    let refreshes = 0;
    vi.stubGlobal("fetch", vi.fn(async (path: string) => {
      if (path === "/api/v1/auth/refresh") {
        refreshes += 1;
        await new Promise((resolve) => setTimeout(resolve, 10));
        return new Response(null, { status: 204 });
      }
      reads += 1;
      return reads <= 10 ? unauthorized() : ok();
    }));
    await Promise.all(Array.from({ length: 10 }, () => apiFetch("/api/v1/auth/me")));
    expect(refreshes).toBe(1);
    expect(reads).toBe(20);
  });

  it("retries only once if the refreshed request also returns 401", async () => {
    const fetcher = vi.fn(async (path: string) => path.endsWith("/refresh")
      ? new Response(null, { status: 204 }) : unauthorized());
    vi.stubGlobal("fetch", fetcher);
    await expect(apiFetch("/api/v1/auth/me")).rejects.toBeInstanceOf(ApiClientError);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it.each(["login", "refresh"])("never refreshes the %s endpoint", async (endpoint) => {
    const fetcher = vi.fn().mockResolvedValue(unauthorized());
    vi.stubGlobal("fetch", fetcher);
    await expect(apiFetch(`/api/v1/auth/${endpoint}`, { method: "POST" })).rejects.toMatchObject({
      status: 401,
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("does not retry the original request when refresh fails", async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(unauthorized()));
    vi.stubGlobal("fetch", fetcher);
    await expect(apiFetch("/api/v1/auth/me")).rejects.toMatchObject({ status: 401 });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("rechecks identity when a domain request cannot refresh a revoked session", async () => {
    const listener = vi.fn();
    window.addEventListener("insighthr-authority-recheck", listener);
    try {
      const fetcher = vi.fn().mockImplementation(() => Promise.resolve(unauthorized()));
      vi.stubGlobal("fetch", fetcher);
      await expect(apiFetch("/api/v1/ai-reports")).rejects.toMatchObject({ status: 401 });
      expect(listener).toHaveBeenCalledTimes(1);
      expect(fetcher).toHaveBeenCalledTimes(2);
    } finally { window.removeEventListener("insighthr-authority-recheck", listener); }
  });

  it("accepts empty 204 responses and rejects remote URLs", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetcher);
    expect(await apiFetch("/api/v1/auth/logout", { method: "POST" })).toBeUndefined();
    await expect(apiFetch("https://elsewhere.example/api/v1/users")).rejects.toThrow();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

it("discards an old account response even if its transport ignores abort", async () => {
  let release!: (value: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { release = resolve; })));
  const old = apiFetch("/api/v1/employees");
  resetApiSession(); release(ok({ private: "OLD_ACCOUNT" }));
  await expect(old).rejects.toMatchObject({ code: "session_changed" });
  vi.unstubAllGlobals();
});

it("does not replay an old mutation after late refresh completes during logout", async () => {
  resetApiSession();
  let release!: (value: Response) => void;
  const fetcher = vi.fn((path: string) => path.endsWith("/refresh")
    ? new Promise<Response>((resolve) => { release = resolve; }) : Promise.resolve(unauthorized()));
  vi.stubGlobal("fetch", fetcher);
  const old = apiFetch("/api/v1/employee-kpis/id", { method: "PATCH", body: "{}" });
  while (!release) await Promise.resolve();
  resetApiSession(); release(new Response(null, { status: 204 }));
  await expect(old).rejects.toMatchObject({ code: "session_changed" });
  expect(fetcher.mock.calls.filter(([path]) => path.includes("employee-kpis"))).toHaveLength(1);
  vi.unstubAllGlobals();
});

it("does not reveal a delayed JSON body from the previous session", async () => {
  resetApiSession();
  let release!: (value: unknown) => void;
  const response = ok(); response.json = () => new Promise((resolve) => { release = resolve; });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
  const old = apiFetch("/api/v1/ai-reports");
  while (!release) await Promise.resolve();
  resetApiSession(); release({ secret: "OLD_PRIVATE_CONTENT" });
  await expect(old).rejects.toMatchObject({ code: "session_changed" });
  vi.unstubAllGlobals();
});
