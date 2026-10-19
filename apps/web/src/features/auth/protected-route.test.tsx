// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ProtectedRoute } from "./protected-route";

const auth = vi.hoisted(() => ({
  pending: true, signedIn: false, role: "HR", error: null as Error | null,
  replace: vi.fn(), retry: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: auth.replace }) }));
vi.mock("./auth-provider", () => ({ useAuth: () => ({
  pending: auth.pending, user: auth.signedIn ? { role: auth.role } : null,
  error: auth.error, retry: auth.retry,
}) }));

beforeEach(() => {
  vi.clearAllMocks(); auth.pending = true; auth.signedIn = false; auth.role = "HR"; auth.error = null;
});

it("hides protected children during identity/refresh resolution", () => {
  render(<ProtectedRoute><p>Private records</p></ProtectedRoute>);
  expect(screen.queryByText("Private records")).toBeNull();
  expect(auth.replace).not.toHaveBeenCalled();
});

it("redirects only after an anonymous session has resolved", async () => {
  const view = render(<ProtectedRoute><p>Private records</p></ProtectedRoute>);
  auth.pending = false;
  view.rerender(<ProtectedRoute><p>Private records</p></ProtectedRoute>);
  await waitFor(() => expect(auth.replace).toHaveBeenCalledWith("/login"));
  expect(screen.queryByText("Private records")).toBeNull();
});

it("renders authorized children but denies another role", () => {
  auth.pending = false; auth.signedIn = true;
  render(<ProtectedRoute roles={["ADMIN"]}><p>Private records</p></ProtectedRoute>);
  expect(screen.queryByText("Private records")).toBeNull();
  expect(screen.getByRole("alert").textContent).toContain("không có quyền");
});

it("does not turn a network outage into an anonymous redirect", () => {
  auth.pending = false; auth.error = new Error("offline");
  render(<ProtectedRoute><p>Private records</p></ProtectedRoute>);
  expect(screen.getByRole("button", { name: "Thử lại" })).toBeTruthy();
  expect(auth.replace).not.toHaveBeenCalled();
});
