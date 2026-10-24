export class ApiClientError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string,
    public readonly details: Record<string, unknown>[] = []) {
    super(message);
    this.name = "ApiClientError";
  }
}

let refreshPromise: Promise<void> | null = null;
let refreshGeneration = 0;
let sessionEpoch = 0;
let sessionController = new AbortController();

export function resetApiSession(): void {
  sessionEpoch += 1;
  sessionController.abort();
  sessionController = new AbortController();
  refreshPromise = null;
}

function requireSession(epoch: number): void {
  if (epoch !== sessionEpoch) throw new ApiClientError(401, "session_changed", "Phiên đăng nhập đã thay đổi.");
}

function recheckAuthority(path: string, error: unknown): void {
  if (typeof window !== "undefined" && !path.startsWith("/api/v1/auth/") &&
      error instanceof ApiClientError && [401, 403].includes(error.status)) {
    window.dispatchEvent(new Event("insighthr-authority-recheck"));
  }
}

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
  const signal = init.signal ? AbortSignal.any([init.signal, sessionController.signal]) : sessionController.signal;
  return fetch(path, { ...init, signal, headers, credentials: "include", cache: "no-store" });
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

async function refreshSession(epoch: number): Promise<void> {
  if (!refreshPromise) {
    const pending = (async () => {
      const response = await send("/api/v1/auth/refresh", { method: "POST" });
      requireSession(epoch);
      if (!response.ok) throw await errorFrom(response);
      refreshGeneration += 1;
    })();
    refreshPromise = pending;
    void pending.finally(() => { if (refreshPromise === pending) refreshPromise = null; }).catch(() => {});
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
  const epoch = sessionEpoch;
  let response = await send(path, init);
  requireSession(epoch);
  const canRefresh = !options.skipRefresh &&
    !["/api/v1/auth/login", "/api/v1/auth/refresh"].includes(path.split("?")[0] ?? path);
  if (response.status === 401 && canRefresh) {
    if (generation === refreshGeneration) {
      try { await refreshSession(epoch); }
      catch (error) { requireSession(epoch); recheckAuthority(path, error); throw error; }
    }
    requireSession(epoch);
    response = await send(path, init);
    requireSession(epoch);
  }
  if (!response.ok) {
    const error = await errorFrom(response);
    requireSession(epoch);
    recheckAuthority(path, error);
    throw error;
  }
  if (response.status === 204) return undefined as T;
  const value: T = await response.json();
  requireSession(epoch);
  return value;
}
