export class ApiClientError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string,
    public readonly details: Record<string, unknown>[] = []) {
    super(message);
    this.name = "ApiClientError";
  }
}

let refreshPromise: Promise<void> | null = null;
let refreshGeneration = 0;

function csrfCookie(): string | null {
  if (typeof document === "undefined") return null;
  const value = document.cookie.split(";").map((part) => part.trim())
    .find((part) => part.startsWith("insighthr_csrf="))?.slice("insighthr_csrf=".length);
  if (!value) return null;
  try { return decodeURIComponent(value); } catch { return null; }
}

async function send(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  headers.delete("X-CSRF-Token");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = csrfCookie();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  if (init.body && !headers.has("Content-Type") && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  return fetch(path, { ...init, headers, credentials: "include", cache: "no-store" });
}

async function errorFrom(response: Response): Promise<ApiClientError> {
  const body: unknown = await response.json().catch(() => null);
  if (body && typeof body === "object" && "error" in body) {
    const error = body.error;
    if (error && typeof error === "object" && "code" in error && "message" in error &&
        typeof error.code === "string" && typeof error.message === "string") {
      const details = "details" in error && Array.isArray(error.details)
        ? error.details.filter((item): item is Record<string, unknown> => !!item && typeof item === "object" && !Array.isArray(item)) : [];
      return new ApiClientError(response.status, error.code, error.message, details);
    }
  }
  return new ApiClientError(response.status, "request_failed", "Yêu cầu không thành công.");
}

async function refreshSession(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const response = await send("/api/v1/auth/refresh", { method: "POST" });
      if (!response.ok) throw await errorFrom(response);
      refreshGeneration += 1;
    })().finally(() => { refreshPromise = null; });
  }
  await refreshPromise;
}

export async function apiFetch<T = void>(
  path: string, init: RequestInit = {}, options: { skipRefresh?: boolean } = {},
): Promise<T> {
  if (!path.startsWith("/api/v1/") || path.includes("\\") || path.includes("..")) {
    throw new Error("API requests must use the same-origin /api/v1/ prefix");
  }
  const generation = refreshGeneration;
  let response = await send(path, init);
  const canRefresh = !options.skipRefresh &&
    !["/api/v1/auth/login", "/api/v1/auth/refresh"].includes(path.split("?")[0] ?? path);
  if (response.status === 401 && canRefresh) {
    if (generation === refreshGeneration) await refreshSession();
    response = await send(path, init);
  }
  if (!response.ok) throw await errorFrom(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
