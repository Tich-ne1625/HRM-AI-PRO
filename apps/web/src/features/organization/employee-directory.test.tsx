// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { EmployeeDirectory } from "./employee-directory";

const mocks = vi.hoisted(() => ({ role: "HR", employees: vi.fn(), references: vi.fn() }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { role: mocks.role, employee_id: "self" } }) }));
vi.mock("./api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./api")>(), organizationApi: mocks,
}));

function mount() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <EmployeeDirectory />
  </QueryClientProvider>);
}
beforeEach(() => {
  vi.clearAllMocks(); mocks.role = "HR";
  mocks.employees.mockResolvedValue({ items: [{ id: "alice", employee_code: "E-01", display_name: "Alice",
    department_name: "Engineering", position_title: "Developer", employment_status: "ACTIVE" }], total: 21, page: 1, page_size: 20 });
  mocks.references.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
});

it("lists scoped employees, links details, and requests the next page", async () => {
  const user = userEvent.setup(); mount();
  expect((await screen.findByRole("link", { name: "Alice" })).getAttribute("href")).toBe("/employees/alice");
  await user.click(screen.getByRole("button", { name: "Trang sau" }));
  await waitFor(() => expect(mocks.employees).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
});

it("submits server-side search and resets pagination", async () => {
  const user = userEvent.setup(); mount();
  await screen.findByText("Alice");
  await user.type(screen.getByLabelText("Tìm nhân viên"), "Alice{Enter}");
  await waitFor(() => expect(mocks.employees).toHaveBeenLastCalledWith(expect.objectContaining({ q: "Alice", page: 1 })));
});

it("hides HR controls from employees and rejects ADMIN without querying", async () => {
  mocks.role = "EMPLOYEE"; const view = mount();
  await screen.findByText("Alice");
  expect(screen.queryByRole("button", { name: "Thêm nhân viên" })).toBeNull();
  view.unmount(); vi.clearAllMocks(); mocks.role = "ADMIN"; mount();
  expect(mocks.employees).not.toHaveBeenCalled();
});

it("shows an empty state and no fabricated records", async () => {
  mocks.employees.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  mount();
  expect(await screen.findByText("Không có nhân viên phù hợp.")).toBeTruthy();
});
