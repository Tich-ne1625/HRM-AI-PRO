// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { AccountPanel } from "./account-panel";

const mocks = vi.hoisted(() => ({ changePassword: vi.fn(), logout: vi.fn(), replace: vi.fn() }));
vi.mock("./api", () => ({ authApi: { changePassword: mocks.changePassword } }));
vi.mock("./auth-provider", () => ({ useAuth: () => ({
  user: { email: "hr@example.com", role: "HR" },
  logout: { mutateAsync: mocks.logout, isPending: false },
}) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: mocks.replace }) }));

beforeEach(() => { vi.clearAllMocks(); mocks.changePassword.mockResolvedValue(undefined); });
function mount() {
  render(<QueryClientProvider client={new QueryClient()}><AccountPanel /></QueryClientProvider>);
}

it("shows identity and signs out", async () => {
  mocks.logout.mockResolvedValue(undefined);
  const user = userEvent.setup(); mount();
  expect(screen.getByText("hr@example.com")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Đăng xuất" }));
  await waitFor(() => expect(mocks.logout).toHaveBeenCalled());
  expect(mocks.replace).toHaveBeenCalledWith("/login");
});

it("validates password confirmation before calling the API", async () => {
  const user = userEvent.setup(); mount();
  await user.type(screen.getByLabelText("Mật khẩu hiện tại"), "original-password");
  await user.type(screen.getByLabelText("Mật khẩu mới"), "replacement-password");
  await user.type(screen.getByLabelText("Xác nhận mật khẩu mới"), "different-password");
  await user.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));
  expect((await screen.findByRole("alert")).textContent).toContain("không khớp");
  expect(mocks.changePassword).not.toHaveBeenCalled();
  await user.clear(screen.getByLabelText("Xác nhận mật khẩu mới"));
  await user.type(screen.getByLabelText("Xác nhận mật khẩu mới"), "replacement-password");
  await user.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));
  await waitFor(() => expect(mocks.changePassword).toHaveBeenCalledWith({
    old_password: "original-password", new_password: "replacement-password",
  }, expect.anything()));
});
