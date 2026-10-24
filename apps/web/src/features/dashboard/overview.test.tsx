// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { DashboardOverview } from "./overview";

const mocks = vi.hoisted(() => ({ role: "HR", get: vi.fn() }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { id: "u1", role: mocks.role } }) }));
vi.mock("./api", () => ({ dashboardApi: { get: mocks.get } }));
const overview = { role: "HR", pending_feedback: 2, active_employees: 8,
  cycles: [{ id: "c1", name: "Hiện tại", status: "ACTIVE" }, { id: "c2", name: "Lịch sử", status: "CLOSED" }],
  selected_cycle: { id: "c1", name: "Hiện tại", status: "ACTIVE" }, participants: 5,
  finalized: 1, current: 1, stale: 1, not_calculated: 2, awaiting_completion: 4,
  average: "84.90", sample_size: 2, score_bands: { "<65": 0, "65-<80": 0, "80-<90": 2, "≥90": 0 },
  kpis_assigned: 10, kpis_entered: 9, kpi_entry_percent: "90.00",
  departments: [{ id: "d1", name: "Kỹ thuật", participants: 3, sample_size: 1, average: "82.80" }],
  recent_activities: [{ id: "event1", action: "performance.calculated", occurred_at: "2026-10-24T00:00:00Z", employee_id: "e1", display_name: "An", cycle_id: "c1" }] };
function mount() {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><DashboardOverview /></QueryClientProvider>);
}
beforeEach(() => { vi.resetAllMocks(); mocks.role = "HR"; mocks.get.mockResolvedValue(overview); });
it("shows scoped metrics, sample sizes and links to existing workflows", async () => {
  mount(); await screen.findByText("84.90");
  expect(screen.getByText("2 kết quả hiện hành / đã chốt")).toBeTruthy();
  expect(screen.getByText("90.00%")).toBeTruthy();
  expect(screen.getByRole("link", { name: /Mở chu kỳ/ }).getAttribute("href")).toBe("/review-cycles/c1");
  expect(screen.getByRole("progressbar", { name: "80-<90 điểm: 2 người" })).toHaveProperty("value", 2);
  expect(screen.getByText("Đã tính điểm đánh giá")).toBeTruthy();
  expect(screen.getByRole("link", { name: "An →" }).getAttribute("href")).toBe("/employees/e1/performance?cycle_id=c1");
});
it("changes cycles and refreshes with read requests only", async () => {
  const user = userEvent.setup(); mount(); await screen.findByText("84.90");
  await user.selectOptions(screen.getByLabelText("Chu kỳ đánh giá"), "c2");
  await waitFor(() => expect(mocks.get).toHaveBeenCalledWith("c2"));
  await user.click(await screen.findByRole("button", { name: "Tải lại" }));
  expect(mocks.get.mock.calls.length).toBeGreaterThanOrEqual(3);
});
it("does not turn an empty average into a zero or draw an empty score chart", async () => {
  mocks.get.mockResolvedValue({ ...overview, average: null, sample_size: 0 });
  mount(); await screen.findByText("Chưa có điểm hợp lệ để thống kê.");
  expect(screen.queryByRole("progressbar")).toBeNull();
  expect(screen.queryByText("84.90")).toBeNull();
});
it("shows ADMIN account controls without performance screens", async () => {
  mocks.role = "ADMIN";
  mocks.get.mockResolvedValue({ role: "ADMIN", pending_feedback: 0, active_accounts: 10, inactive_accounts: 1, account_roles: { ADMIN: 1, HR: 1, MANAGER: 2, EMPLOYEE: 7 } });
  mount(); await screen.findByText("Tài khoản hoạt động");
  expect(screen.getByRole("link", { name: /Quản lý tài khoản/ })).toBeTruthy();
  expect(screen.queryByLabelText("Chu kỳ đánh giá")).toBeNull();
  expect(screen.queryByText("Điểm trung bình hợp lệ")).toBeNull();
});
it("offers retry on a failed load and handles an unlinked account", async () => {
  mocks.get.mockRejectedValueOnce(new Error("unavailable"));
  const user = userEvent.setup(); mount(); await screen.findByRole("alert");
  mocks.get.mockResolvedValue({ ...overview, cycles: [], selected_cycle: null, participants: 0 });
  await user.click(screen.getByRole("button", { name: "Tải lại" }));
  await screen.findByText(/Chưa có người tham gia/);
  expect(screen.getByRole("link", { name: /Mở hộp việc/ })).toBeTruthy();
});
it("hides cached metrics and activities when a refresh is denied or fails", async () => {
  const user = userEvent.setup(); mount(); await screen.findByText("84.90");
  mocks.get.mockRejectedValue(new Error("authority changed"));
  await user.click(screen.getByRole("button", { name: "Tải lại" }));
  await screen.findByRole("alert");
  expect(screen.queryByText("84.90")).toBeNull();
  expect(screen.queryByText("Đã tính điểm đánh giá")).toBeNull();
  expect(screen.queryByRole("link", { name: /Mở chu kỳ để/ })).toBeNull();
});
