// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { WorkspaceRouteAccess } from "./route-access";
import { workspaceRouteAllowed } from "./navigation-model";

const state = vi.hoisted(() => ({ role: "EMPLOYEE", path: "/kpis" }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { role: state.role } }) }));
vi.mock("next/navigation", () => ({ usePathname: () => state.path }));
beforeEach(() => { state.role = "EMPLOYEE"; state.path = "/kpis"; });

it.each(["EMPLOYEE", "MANAGER", "ADMIN"])("does not mount HR management pages for %s even with a direct URL", (role) => {
  state.role = role;
  const load = vi.fn();
  function Management() { load(); return <p>Secret management controls</p>; }
  render(<WorkspaceRouteAccess><Management /></WorkspaceRouteAccess>);
  expect(load).not.toHaveBeenCalled();
  expect(screen.queryByText("Secret management controls")).toBeNull();
});

it("mounts an HR management page for HR", () => {
  state.role = "HR";
  render(<WorkspaceRouteAccess><p>Danh mục</p></WorkspaceRouteAccess>);
  expect(screen.getByText("Danh mục")).toBeTruthy();
});

it("keeps reviewer inbox available to every role while isolating account administration", () => {
  for (const role of ["HR", "MANAGER", "EMPLOYEE", "ADMIN"] as const) {
    expect(workspaceRouteAllowed(role, "/feedback/a1")).toBe(true);
    expect(workspaceRouteAllowed(role, "/admin/users")).toBe(role === "ADMIN");
    expect(workspaceRouteAllowed(role, "/feedback-administration")).toBe(role === "HR");
    expect(workspaceRouteAllowed(role, "/review-cycles")).toBe(role !== "ADMIN");
  }
});
