// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { LoginForm, safeRedirect } from "./login-form";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(), login: vi.fn(), pending: false, signedIn: false,
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }), useSearchParams: () => new URLSearchParams(),
}));
vi.mock("./auth-provider", () => ({ useAuth: () => ({
  user: mocks.signedIn ? { email: "a@example.com" } : null, pending: false,
  login: { mutateAsync: mocks.login, isPending: mocks.pending },
}) }));

beforeEach(() => { vi.clearAllMocks(); mocks.pending = false; mocks.signedIn = false; });

it("submits labeled credentials with Enter and redirects to dashboard", async () => {
  const user = userEvent.setup();
  mocks.login.mockResolvedValue({});
  render(<LoginForm demoEnabled={false} />);
  await user.type(screen.getByLabelText("Email"), "a@example.com");
  await user.type(screen.getByLabelText("Mật khẩu"), "original-password{Enter}");
  await waitFor(() => expect(mocks.login).toHaveBeenCalledWith({
    email: "a@example.com", password: "original-password",
  }));
  expect(mocks.replace).toHaveBeenCalledWith("/dashboard");
});

it("shows a generic credential error without exposing submitted values", async () => {
  mocks.login.mockRejectedValue(new Error("private-db-details"));
  const user = userEvent.setup();
  render(<LoginForm demoEnabled={false} />);
  await user.type(screen.getByLabelText("Email"), "a@example.com");
  await user.type(screen.getByLabelText("Mật khẩu"), "wrong-password");
  await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
  expect((await screen.findByRole("alert")).textContent).toBe("Email hoặc mật khẩu không đúng.");
});

it("disables submit while pending and redirects an authenticated visitor", async () => {
  mocks.pending = true;
  const view = render(<LoginForm demoEnabled={false} />);
  expect((screen.getByRole("button", { name: "Đang đăng nhập…" }) as HTMLButtonElement).disabled).toBe(true);
  mocks.signedIn = true;
  view.rerender(<LoginForm />);
  await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/dashboard"));
});

it.each(["https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)"])(
  "rejects unsafe redirects: %s", (value) => { expect(safeRedirect(value)).toBe("/dashboard"); },
);
it("keeps internal redirects", () => { expect(safeRedirect("/admin/users?page=2")).toBe("/admin/users?page=2"); });

it("starts with HR demo and authenticates with the supplied password", async () => {
  const user = userEvent.setup();
  mocks.login.mockResolvedValue({});
  render(<LoginForm />);
  expect(screen.getByRole("button", { name: /^Nhân sự/ }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByText("hr.demo@example.com")).toBeTruthy();
  await user.type(screen.getByLabelText("Mật khẩu"), "demo-password");
  await user.click(screen.getByRole("button", { name: "Vào trải nghiệm · Nhân sự" }));
  await waitFor(() => expect(mocks.login).toHaveBeenCalledWith({ email: "hr.demo@example.com", password: "demo-password" }));
});

it("selects named accounts across roles without submitting or losing the entered password", async () => {
  const user = userEvent.setup();
  mocks.login.mockResolvedValue({});
  render(<LoginForm />);
  await user.type(screen.getByLabelText("Mật khẩu"), "demo-password");
  await user.click(screen.getByRole("button", { name: /^Quản lý/ }));
  await user.selectOptions(screen.getByLabelText("Người dùng thử"), "sales.manager.demo@example.com");
  expect(screen.getByText("sales.manager.demo@example.com")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /^Nhân viên/ }));
  expect((screen.getByLabelText("Người dùng thử") as HTMLSelectElement).value).toBe("binh.demo@example.com");
  await user.selectOptions(screen.getByLabelText("Người dùng thử"), "linh.demo@example.com");
  expect(mocks.login).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Vào trải nghiệm · Nhân viên" }));
  await waitFor(() => expect(mocks.login).toHaveBeenCalledWith({ email: "linh.demo@example.com", password: "demo-password" }));
});

it("allows a separate account and returns to demo with the correct email", async () => {
  const user = userEvent.setup();
  render(<LoginForm />);
  await user.click(screen.getByRole("button", { name: /^Quản trị/ }));
  await user.click(screen.getByRole("button", { name: "Dùng tài khoản riêng" }));
  expect((screen.getByLabelText("Email") as HTMLInputElement).value).toBe("");
  await user.type(screen.getByLabelText("Email"), "own@example.com");
  await user.click(screen.getByRole("button", { name: "Chọn tài khoản demo" }));
  expect(screen.getByText("admin.demo@example.com")).toBeTruthy();
});

it("requires a password and shows failures without treating a role choice as authentication", async () => {
  const user = userEvent.setup();
  mocks.login.mockRejectedValue(new Error("private details"));
  render(<LoginForm />);
  await user.click(screen.getByRole("button", { name: "Vào trải nghiệm · Nhân sự" }));
  expect(await screen.findByText("Nhập mật khẩu.")).toBeTruthy();
  expect(mocks.login).not.toHaveBeenCalled();
  await user.type(screen.getByLabelText("Mật khẩu"), "wrong-password");
  await user.click(screen.getByRole("button", { name: "Vào trải nghiệm · Nhân sự" }));
  expect(await screen.findByText("Email hoặc mật khẩu không đúng.")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /^Quản lý/ }));
  expect(screen.queryByText("Email hoặc mật khẩu không đúng.")).toBeNull();
});
