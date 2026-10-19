// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { UserManagement } from "./user-management";

const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), update: vi.fn(), role: "ADMIN" }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { role: mocks.role } }) }));
vi.mock("./users-api", () => ({ usersApi: mocks }));

function mount() {
  return render(<QueryClientProvider client={new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })}><UserManagement /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks(); mocks.role = "ADMIN";
  mocks.list.mockResolvedValue({ items: [{
    id: "target", email: "hr@example.com", role: "HR", is_active: true,
  }], total: 1, page: 1, page_size: 20 });
  mocks.create.mockResolvedValue({}); mocks.update.mockResolvedValue({});
});

it("does not request user data for nonadmins", () => {
  mocks.role = "HR"; mount();
  expect(mocks.list).not.toHaveBeenCalled();
  expect(screen.getByRole("alert").textContent).toContain("không có quyền");
});

it("lists accounts and submits a create form", async () => {
  const user = userEvent.setup(); mount();
  expect(await screen.findByText("hr@example.com")).toBeTruthy();
  await user.type(screen.getByLabelText("Email tài khoản mới"), "new@example.com");
  await user.type(screen.getByLabelText("Mật khẩu ban đầu"), "initial-password");
  await user.click(screen.getByRole("button", { name: "Tạo tài khoản" }));
  await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({
    email: "new@example.com", password: "initial-password", role: "EMPLOYEE",
  }, expect.anything()));
});

it("requires confirmation before deactivation and sends role changes", async () => {
  const user = userEvent.setup(); mount();
  await screen.findByText("hr@example.com");
  await user.selectOptions(screen.getByLabelText("Vai trò của hr@example.com"), "MANAGER");
  await waitFor(() => expect(mocks.update).toHaveBeenCalledWith("target", { role: "MANAGER" }));
  await user.click(screen.getByRole("button", { name: "Vô hiệu hóa hr@example.com" }));
  expect(mocks.update).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole("button", { name: "Xác nhận vô hiệu hóa" }));
  await waitFor(() => expect(mocks.update).toHaveBeenCalledWith("target", { is_active: false }));
});
