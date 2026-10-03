import { afterEach, describe, expect, it, vi } from "vitest";

import { getApiStatus } from "./api";

describe("getApiStatus", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns available for the valid liveness contract", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", service: "api" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await expect(getApiStatus(fetcher)).resolves.toEqual({
      kind: "available",
      service: "api",
    });
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/health/live",
      expect.objectContaining({ cache: "no-store", signal: expect.any(AbortSignal) }),
    );
  });

  it.each([
    ["non-success response", async () => new Response("unavailable", { status: 503 })],
    ["malformed JSON", async () => new Response("not-json", { status: 200 })],
    [
      "unknown payload",
      async () =>
        new Response(JSON.stringify({ status: "healthy", service: "api" }), { status: 200 }),
    ],
  ])("returns unavailable for %s", async (_name, responseFactory) => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(await responseFactory());

    await expect(getApiStatus(fetcher)).resolves.toEqual({ kind: "unavailable" });
  });

  it("returns unavailable for a network rejection", async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new Error("connection refused"));

    await expect(getApiStatus(fetcher)).resolves.toEqual({ kind: "unavailable" });
  });

  it("aborts a request that exceeds three seconds", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn<typeof fetch>((_input, init) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });

    const status = getApiStatus(fetcher);
    await vi.advanceTimersByTimeAsync(3_000);

    await expect(status).resolves.toEqual({ kind: "unavailable" });
  });
});

