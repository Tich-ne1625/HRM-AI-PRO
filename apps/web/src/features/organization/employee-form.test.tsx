// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { EmployeeForm } from "./employee-form";

const mocks = vi.hoisted(() => ({ references: vi.fn(), employees: vi.fn(), saveEmployee: vi.fn(), lookup: vi.fn(), saved: vi.fn() }));
vi.mock("./api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./api")>(), organizationApi: mocks,
}));
beforeEach(() => {
  vi.clearAllMocks();
  mocks.references.mockImplementation(async (kind: string) => ({ items: [{ id: kind === "departments" ? "eng" : "dev", code: "CODE", ...(kind === "departments" ? { name: "Engineering" } : { title: "Developer" }), is_active: true }], total: 1, page: 1, page_size: 20 }));
  mocks.employees.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  mocks.saveEmployee.mockResolvedValue({ id: "new" });
  mocks.lookup.mockResolvedValue({ items: [{ id: "account", email: "employee@example.com", is_active: true, employee_id: null }] });
});

function mount() {
  render(<QueryClientProvider client={new QueryClient()}><EmployeeForm onSaved={mocks.saved} /></QueryClientProvider>);
}
it("creates an employee using labeled reference selectors", async () => {
  const user = userEvent.setup(); mount();
  await screen.findByRole("option", { name: "Engineering (CODE)" });
  await user.type(screen.getByLabelText("Mã nhân viên"), "emp-new");
  await user.type(screen.getByLabelText("Họ và tên"), "New Employee");
  await user.selectOptions(screen.getByLabelText("Phòng ban"), "eng");
  await user.selectOptions(screen.getByLabelText("Chức danh"), "dev");
  await user.click(screen.getByRole("button", { name: "Lưu hồ sơ" }));
  await waitFor(() => expect(mocks.saveEmployee).toHaveBeenCalledWith(null, {
    employee_code: "EMP-NEW", display_name: "New Employee", department_id: "eng", position_id: "dev",
    manager_id: null, user_id: null, employment_status: "ACTIVE",
  }));
  expect(mocks.saved).toHaveBeenCalled();
});

it("looks up one exact email before linking an account", async () => {
  const user = userEvent.setup(); mount();
  await user.type(screen.getByLabelText("Email tài khoản cần liên kết"), "employee@example.com");
  await user.click(screen.getByRole("button", { name: "Tìm tài khoản" }));
  expect(await screen.findByText("employee@example.com")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Liên kết tài khoản này" }));
  expect(screen.getByText("Đã chọn tài khoản: employee@example.com")).toBeTruthy();
  expect(mocks.lookup).toHaveBeenCalledWith("employee@example.com");
});

it("keeps a chosen manager when searching a different options page", async () => {
  mocks.employees.mockResolvedValue({ items: [{ id: "manager", display_name: "Manager", employee_code: "MGR" }], total: 1, page: 1, page_size: 20 });
  const user = userEvent.setup(); mount();
  await screen.findByRole("option", { name: "Manager (MGR)" });
  await user.selectOptions(screen.getByLabelText("Người quản lý"), "manager");
  mocks.employees.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  await user.type(screen.getByLabelText("Tìm người quản lý"), "none");
  await waitFor(() => expect(mocks.employees).toHaveBeenLastCalledWith(expect.objectContaining({ q: "none" })));
  expect((screen.getByLabelText("Người quản lý") as HTMLSelectElement).value).toBe("manager");
});
