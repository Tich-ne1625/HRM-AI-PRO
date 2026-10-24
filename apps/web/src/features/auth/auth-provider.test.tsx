// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AuthProvider } from "./auth-provider";
import { useAuth } from "./auth-provider";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { ProtectedRoute } from "./protected-route";

const nav = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => nav }));
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });

function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <AuthProvider><ProtectedRoute><p>Protected account</p></ProtectedRoute></AuthProvider>
  </QueryClientProvider>);
}

const denied = () => new Response(JSON.stringify({
  error: { code: "authentication_required", message: "Authentication required", details: [] },
}), { status: 401 });

it("waits for refresh before showing protected content", async () => {
  let calls = 0;
  let release: (() => void) | undefined;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  vi.stubGlobal("fetch", vi.fn(async (path: string) => {
    if (path.endsWith("/refresh")) { await gate; return new Response(null, { status: 204 }); }
    calls += 1;
    return calls === 1 ? denied() : new Response(JSON.stringify({
      id: "user", email: "hr@example.com", role: "HR", is_active: true, employee_id: null,
    }));
  }));
  mount();
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  expect(screen.queryByText("Protected account")).toBeNull();
  expect(nav.replace).not.toHaveBeenCalled();
  release?.();
  expect(await screen.findByText("Protected account")).toBeTruthy();
  expect(nav.replace).not.toHaveBeenCalled();
});

it("redirects a revoked or inactive session after refresh is rejected", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(denied())));
  mount();
  await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/login"));
  expect(screen.queryByText("Protected account")).toBeNull();
});

it("purges other caches and local form state when the server changes role", async () => {
  let role = "HR";
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
    id: "same-user", email: "fictional@example.com", role, is_active: true, employee_id: "e1",
  }))));
  function Form() {
    const { user } = useAuth(); const [text, setText] = useState("");
    return <><p>{user?.role}</p><input aria-label="Draft" value={text} onChange={(e) => setText(e.target.value)} /></>;
  }
  render(<QueryClientProvider client={client}><AuthProvider><ProtectedRoute><Form /></ProtectedRoute></AuthProvider></QueryClientProvider>);
  await screen.findByText("HR");
  await userEvent.setup().type(screen.getByLabelText("Draft"), "PRIVATE_DRAFT");
  client.setQueryData(["feedback", "administration"], { secret: "PRIVATE_CACHE" });
  role = "MANAGER";
  await act(async () => { await client.invalidateQueries({ queryKey: ["auth", "me"] }); });
  await screen.findByText("MANAGER");
  expect(screen.getByLabelText("Draft")).toHaveProperty("value", "");
  expect(client.getQueryData(["feedback", "administration"])).toBeUndefined();
  client.clear();
});
