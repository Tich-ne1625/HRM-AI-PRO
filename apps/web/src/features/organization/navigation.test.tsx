// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { WorkspaceHeader, WorkspaceNavigation } from "./navigation";

const state = vi.hoisted(() => ({ role: "HR", path: "/review-cycles/c1" }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { role: state.role } }) }));
vi.mock("next/navigation", () => ({ usePathname: () => state.path }));
beforeEach(() => { state.role = "HR"; state.path = "/review-cycles/c1"; });
it("marks the current section and groups links by task", () => {
  render(<WorkspaceNavigation />);
  expect(screen.getByRole("link", { name: "Chu kỳ đánh giá" }).getAttribute("aria-current")).toBe("page");
  expect(screen.getByRole("link", { name: "Phân công phản hồi" }).getAttribute("href")).toBe("/feedback-administration");
});
it("ADMIN has a reviewer inbox and system controls without HR reports", () => {
  state.role = "ADMIN"; render(<WorkspaceNavigation />);
  expect(screen.getByRole("link", { name: "Phản hồi của tôi" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Quản lý tài khoản" })).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Phân công phản hồi" })).toBeNull();
  expect(screen.queryByRole("link", { name: "Nhân viên" })).toBeNull();
});
it("mobile navigation opens with a button and closes on link selection", async () => {
  const user = userEvent.setup(); render(<WorkspaceNavigation />);
  await user.click(screen.getByRole("button", { name: "Mở menu" }));
  expect(screen.getByRole("button", { name: "Đóng menu" }).getAttribute("aria-expanded")).toBe("true");
  screen.getByRole("link", { name: "Phản hồi của tôi" }).addEventListener("click", (event) => event.preventDefault());
  await user.click(screen.getByRole("link", { name: "Phản hồi của tôi" }));
  expect(screen.getByRole("button", { name: "Mở menu" }).getAttribute("aria-expanded")).toBe("false");
});
it("places the report under the evaluation header tab", () => {
  state.path = "/employees/e1/performance"; render(<WorkspaceHeader />);
  expect(screen.getByRole("link", { name: "Đánh giá hiệu suất" }).getAttribute("aria-current")).toBe("location");
  expect(screen.getByRole("link", { name: "Tổ chức" }).getAttribute("aria-current")).toBeNull();
});
it("shows ADMIN system tabs without HR workspace shortcuts", () => {
  state.role = "ADMIN"; render(<WorkspaceHeader />);
  expect(screen.getByRole("link", { name: "Quản trị hệ thống" })).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Đánh giá hiệu suất" })).toBeNull();
});
it("marks evaluation without removing the other fixed HR sections", () => {
  state.path = "/employees/e1/performance"; render(<WorkspaceNavigation />);
  expect(screen.getByRole("link", { name: "Chu kỳ đánh giá" }).getAttribute("aria-current")).toBe("page");
  expect(screen.getByRole("link", { name: "Nhân viên" })).toBeTruthy();
});

it("keeps the same HR menu when switching to organization", () => {
  state.path = "/employees"; render(<><WorkspaceHeader /><WorkspaceNavigation /></>);
  expect(screen.getByRole("link", { name: "Nhân viên" }).getAttribute("aria-current")).toBe("page");
  expect(screen.getByRole("link", { name: "Phòng ban" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Danh mục KPI" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Đánh giá hiệu suất" })).toBeTruthy();
});

it.each(["MANAGER", "EMPLOYEE"])("hides HR catalogs and administration from %s", (role) => {
  state.role = role;
  render(<WorkspaceNavigation />);
  for (const label of ["Phòng ban", "Chức danh", "Danh mục KPI", "Phân công phản hồi", "Quản lý tài khoản", "Cấu hình chấm điểm"]) {
    expect(screen.queryByRole("link", { name: label })).toBeNull();
  }
  expect(screen.getByRole("link", { name: "Chu kỳ đánh giá" })).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Nhân viên trực tiếp" }) !== null).toBe(role === "MANAGER");
});

it("keeps identical sidebar destinations across every HR top-level tab", () => {
  const view = render(<WorkspaceNavigation />);
  const hrefs = () => screen.getAllByRole("link").map((link) => link.getAttribute("href"));
  const original = hrefs();
  for (const path of ["/employees", "/account", "/dashboard", "/kpis", "/feedback", "/ai-reports"]) {
    state.path = path;
    view.rerender(<WorkspaceNavigation />);
    expect(hrefs()).toEqual(original);
  }
});
it("keeps saved AI advice in evaluation navigation and hides it from ADMIN", () => {
  state.path = "/ai-reports";
  const view = render(<><WorkspaceHeader /><WorkspaceNavigation /></>);
  expect(screen.getByRole("link", { name: "Đánh giá hiệu suất" }).getAttribute("aria-current")).toBe("location");
  expect(screen.getByRole("link", { name: "Tư vấn AI đã lưu" }).getAttribute("aria-current")).toBe("page");
  state.role = "ADMIN"; view.rerender(<><WorkspaceHeader /><WorkspaceNavigation /></>);
  expect(screen.queryByRole("link", { name: "Tư vấn AI đã lưu" })).toBeNull();
});
