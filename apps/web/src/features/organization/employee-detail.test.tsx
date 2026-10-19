// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { EmployeeDetail } from "./employee-detail";
import { ApiClientError } from "../../lib/api-client";

const mocks = vi.hoisted(() => ({ role: "EMPLOYEE", employee: vi.fn() }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { role: mocks.role } }) }));
vi.mock("./api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./api")>(), organizationApi: mocks,
}));
function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <EmployeeDetail id="alice" />
  </QueryClientProvider>);
}
beforeEach(() => {
  vi.clearAllMocks(); mocks.role = "EMPLOYEE";
  mocks.employee.mockResolvedValue({ id: "alice", employee_code: "E-01", display_name: "Alice",
    department_name: "Engineering", position_title: "Developer", manager_name: "Manager",
    employment_status: "ACTIVE", user_id: "account" });
});
it("shows authorized detail without an edit control for employees", async () => {
  mount(); expect(await screen.findByRole("heading", { name: "Alice" })).toBeTruthy();
  expect(screen.getByText("Engineering")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Chỉnh sửa hồ sơ" })).toBeNull();
});
it("shows the same not-found message for missing or out-of-scope UUIDs", async () => {
  mocks.employee.mockRejectedValue(new ApiClientError(404, "employee_not_found", "Employee not found"));
  mount(); expect((await screen.findByRole("alert")).textContent).toContain("Không tìm thấy hồ sơ trong phạm vi truy cập");
});
