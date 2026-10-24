import { NextRequest } from "next/server";
import { afterEach, expect, it, vi } from "vitest";
import { proxy } from "./proxy";

afterEach(() => vi.unstubAllEnvs());
it("uses fresh script nonces, no production eval and private HTML", () => {
  vi.stubEnv("NODE_ENV", "production"); vi.stubEnv("APP_ENV", "development");
  const a = proxy(new NextRequest("http://localhost:3000/login"));
  const b = proxy(new NextRequest("http://localhost:3000/login"));
  const policy = a.headers.get("content-security-policy")!;
  expect(policy).toContain("'strict-dynamic'");
  expect(policy).not.toContain("unsafe-eval");
  expect(policy).not.toBe(b.headers.get("content-security-policy"));
  expect(a.headers.get("cache-control")).toBe("no-store");
  expect(a.headers.has("strict-transport-security")).toBe(false);
});
it("emits HSTS/upgrade only for explicit production HTTPS", () => {
  vi.stubEnv("APP_ENV", "production"); vi.stubEnv("WEB_ORIGIN", "https://office.example.com");
  const response = proxy(new NextRequest("https://office.example.com/login"));
  expect(response.headers.get("strict-transport-security")).toContain("max-age=");
  expect(response.headers.get("content-security-policy")).toContain("upgrade-insecure-requests");
});
