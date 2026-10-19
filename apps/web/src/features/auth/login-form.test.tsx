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

it("submits labeled credentials with Enter and redirects to account", async () => {
  const user = userEvent.setup();
  mocks.login.mockResolvedValue({});
  render(<LoginForm />);
  await user.type(screen.getByLabelText("Email"), "a@example.com");
  await user.type(screen.getByLabelText("Mật khẩu"), "original-password{Enter}");
  await waitFor(() => expect(mocks.login).toHaveBeenCalledWith({
    email: "a@example.com", password: "original-password",
  }));
  expect(mocks.replace).toHaveBeenCalledWith("/account");
});

it("shows a generic credential error without exposing submitted values", async () => {
  mocks.login.mockRejectedValue(new Error("private-db-details"));
  const user = userEvent.setup();
  render(<LoginForm />);
  await user.type(screen.getByLabelText("Email"), "a@example.com");
  await user.type(screen.getByLabelText("Mật khẩu"), "wrong-password");
  await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
  expect((await screen.findByRole("alert")).textContent).toBe("Email hoặc mật khẩu không đúng.");
});

it("disables submit while pending and redirects an authenticated visitor", async () => {
  mocks.pending = true;
  const view = render(<LoginForm />);
  expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
  mocks.signedIn = true;
  view.rerender(<LoginForm />);
  await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/account"));
});

it.each(["https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)"])(
  "rejects unsafe redirects: %s", (value) => { expect(safeRedirect(value)).toBe("/account"); },
);
it("keeps internal redirects", () => { expect(safeRedirect("/admin/users?page=2")).toBe("/admin/users?page=2"); });
