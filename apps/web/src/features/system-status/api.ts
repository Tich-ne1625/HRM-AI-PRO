import { z } from "zod";

import { getApiInternalUrl } from "../../lib/env";

const livenessSchema = z
  .object({
    status: z.literal("ok"),
    service: z.literal("api"),
  })
  .strict();

export type ApiStatus =
  | { kind: "available"; service: "api" }
  | { kind: "unavailable" };

export async function getApiStatus(fetcher: typeof fetch = fetch): Promise<ApiStatus> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3_000);

  try {
    const baseUrl = getApiInternalUrl().replace(/\/$/, "");
    const response = await fetcher(`${baseUrl}/health/live`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      return { kind: "unavailable" };
    }

    const parsed = livenessSchema.safeParse(await response.json());
    if (!parsed.success) {
      return { kind: "unavailable" };
    }
    return { kind: "available", service: parsed.data.service };
  } catch {
    return { kind: "unavailable" };
  } finally {
    clearTimeout(timeout);
  }
}

