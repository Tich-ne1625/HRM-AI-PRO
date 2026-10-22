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
  expect(screen.getByRole("link", { name: "Quản trị phản hồi" }).getAttribute("href")).toBe("/feedback-administration");
});
it("ADMIN has a reviewer inbox and system controls without HR reports", () => {
  state.role = "ADMIN"; render(<WorkspaceNavigation />);
  expect(screen.getByRole("link", { name: "Phản hồi của tôi" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Quản lý tài khoản" })).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Quản trị phản hồi" })).toBeNull();
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
it("keeps employee evaluation pages in the cycle workflow on the left", () => {
  state.path = "/employees/e1/performance"; render(<WorkspaceNavigation />);
  expect(screen.getByRole("link", { name: "Chu kỳ đánh giá" }).getAttribute("aria-current")).toBe("page");
  expect(screen.getByRole("link", { name: "Nhân viên" }).getAttribute("aria-current")).toBeNull();
});
