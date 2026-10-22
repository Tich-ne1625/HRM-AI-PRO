// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiClientError } from "../../lib/api-client";
import { CloseCycle } from "./close-cycle";
import { EvaluationTabs } from "./context-tabs";
import { PerformanceReport } from "./report";
import type { Cycle } from "../cycles/api";

const mocks = vi.hoisted(() => ({ role: "HR", api: { report: vi.fn(), calculate: vi.fn(), context: vi.fn(), finalize: vi.fn(), revisions: vi.fn(), revision: vi.fn(), close: vi.fn() } }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { id: "user", role: mocks.role } }) }));
vi.mock("./api", () => ({ performanceApi: mocks.api }));
const result = { calculation_version: 1, evidence_version: 8, engine_version: "1", calculated_at: "2026-10-22T00:00:00Z", kpi_score: "90.00", feedback_score: "80.00", final_score: "87.00", policy: { schema_version: 1, kpi_weight: "70.00", feedback_weight: "30.00", kpi_cap: "100.00" }, items: [], feedback: { count: 2, mean: "4.00", groups: [{ relationship: "PEER", suppressed: true, count: null, mean: null }], own_submission: null } };
const report = { review_id: "r1", participant_id: "p1", employee_id: "e1", employee_code: "NV01", display_name: "An", cycle_id: "c1", cycle_name: "Quý IV", cycle_status: "ACTIVE", cycle_version: 3, evidence_version: 8, state: "CURRENT", current_result: result, last_calculation: result, readiness: { ready: true, issue_count: 0, issues: [] }, can_calculate: true, can_finalize: true, finalized_at: null, reused: false };
const context = { review_id: "r1", evidence_version: 8, calculation_version: 1, open_optional_count: 1, readiness: report.readiness };
function mount(child: ReactNode) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={cache}>{child}</QueryClientProvider>); return cache;
}
beforeEach(() => {
  vi.resetAllMocks(); mocks.role = "HR";
  mocks.api.report.mockResolvedValue(report); mocks.api.context.mockResolvedValue(context);
  mocks.api.revisions.mockResolvedValue({ items: [result], total: 1, page: 1, page_size: 20 });
  mocks.api.revision.mockResolvedValue(result); mocks.api.calculate.mockResolvedValue(report);
  mocks.api.finalize.mockResolvedValue({ ...report, state: "FINALIZED", can_calculate: false, can_finalize: false });
});
it("does not fetch reports for ADMIN", () => {
  mocks.role = "ADMIN"; mount(<PerformanceReport employeeId="e1" cycleId="c1" />);
  expect(screen.getByRole("alert")).toBeTruthy(); expect(mocks.api.report).not.toHaveBeenCalled();
});
it("shows current totals and retains employee/cycle across functional tabs", async () => {
  mount(<PerformanceReport employeeId="e1" cycleId="c1" />);
  await screen.findByText("Điểm hiệu suất");
  expect(screen.getAllByText("87.00").length).toBeGreaterThan(0);
  expect(screen.getByRole("link", { name: "Phản hồi 360" }).getAttribute("href")).toBe("/employees/e1/feedback?cycle_id=c1");
  expect(screen.getByRole("link", { name: "Kết quả hiệu suất" }).getAttribute("aria-current")).toBe("page");
  expect(screen.getByText(/Chưa đủ ba người/)).toBeTruthy();
});
it("never presents stale totals as the current result", async () => {
  mocks.api.report.mockResolvedValue({ ...report, state: "STALE", current_result: null, can_finalize: false });
  mount(<PerformanceReport employeeId="e1" cycleId="c1" />);
  await screen.findByText("Cần tính lại");
  expect(screen.queryByText("Điểm hiệu suất")).toBeNull();
  expect(screen.queryByRole("button", { name: "Chốt kết quả" })).toBeNull();
  expect(screen.getByRole("heading", { name: "Lịch sử tính điểm" })).toBeTruthy();
});
it("offers actionable readiness links without trying to calculate", async () => {
  mocks.api.report.mockResolvedValue({ ...report, review_id: null, state: "NOT_CALCULATED", current_result: null, can_calculate: false, can_finalize: false, readiness: { ready: false, issue_count: 1, issues: [{ code: "kpi_actual_required", kpi_id: "k1" }] } });
  mount(<PerformanceReport employeeId="e1" cycleId="c1" />);
  await screen.findByText("Có KPI chưa nhập kết quả thực tế.");
  expect(screen.getByRole("link", { name: "Kiểm tra KPI" })).toBeTruthy();
  expect(mocks.api.calculate).not.toHaveBeenCalled();
});
it("requires explicit acknowledgement and sends the reviewed context", async () => {
  const user = userEvent.setup(); mount(<PerformanceReport employeeId="e1" cycleId="c1" />);
  await user.click(await screen.findByRole("button", { name: "Chốt kết quả" }));
  const confirm = await screen.findByRole("button", { name: "Xác nhận chốt kết quả" });
  expect(confirm).toHaveProperty("disabled", true);
  await user.click(screen.getByRole("checkbox")); await user.click(confirm);
  await waitFor(() => expect(mocks.api.finalize).toHaveBeenCalledWith("r1", context));
});
it("requires renewed acknowledgement when the confirmation context changes", async () => {
  const user = userEvent.setup(), cache = mount(<PerformanceReport employeeId="e1" cycleId="c1" />);
  await user.click(await screen.findByRole("button", { name: "Chốt kết quả" }));
  await user.click(await screen.findByRole("checkbox"));
  act(() => { cache.setQueryData(["performance", "finalization", "r1", 8, "user"], { ...context, evidence_version: 9, open_optional_count: 2 }); });
  await waitFor(() => expect(screen.getByRole("checkbox")).toHaveProperty("checked", false));
  expect(screen.getByRole("button", { name: "Xác nhận chốt kết quả" })).toHaveProperty("disabled", true);
});
it("stops repeat submission after conflict until explicit reload", async () => {
  mocks.api.calculate.mockRejectedValue(new ApiClientError(409, "stale_evidence_version", "stale"));
  const user = userEvent.setup(); mount(<PerformanceReport employeeId="e1" cycleId="c1" />);
  await user.click(await screen.findByRole("button", { name: "Tính lại điểm" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Tính lại điểm" })).toHaveProperty("disabled", true);
  expect(mocks.api.calculate).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole("button", { name: "Tải bản mới" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Tính lại điểm" })).toHaveProperty("disabled", false));
});
it("opens history with an explicit historical label", async () => {
  const user = userEvent.setup(); mount(<PerformanceReport employeeId="e1" cycleId="c1" />);
  await user.click(await screen.findByRole("button", { name: "Xem lần 1" }));
  expect(await screen.findByRole("heading", { name: "Đang xem lịch sử · Lần 1" })).toBeTruthy();
  await waitFor(() => expect(mocks.api.revision).toHaveBeenCalledWith("r1", 1));
});
it("renders own comments as plain text", async () => {
  mocks.api.report.mockResolvedValue({ ...report, current_result: { ...result, feedback: { ...result.feedback, own_submission: { rating: 4, comment: "<script>bad()</script>", submitted_at: "2026-10-22T00:00:00Z" } } } });
  mount(<PerformanceReport employeeId="e1" cycleId="c1" />);
  await screen.findByText("<script>bad()</script>"); expect(document.querySelector("script")).toBeNull();
});
it("keeps a finalized report readable without mutation actions", async () => {
  mocks.api.report.mockResolvedValue({ ...report, state: "FINALIZED", can_calculate: false, can_finalize: false });
  mount(<PerformanceReport employeeId="e1" cycleId="c1" />);
  await screen.findByText("Đã chốt kết quả");
  expect(screen.queryByRole("button", { name: "Tính lại điểm" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Chốt kết quả" })).toBeNull();
});
it("captures the cycle version when opening close confirmation", async () => {
  const cycle = { id: "c1", version: 3 } as Cycle;
  mocks.api.close.mockResolvedValue({ id: "c1", status: "CLOSED", version: 4 });
  const user = userEvent.setup(); mount(<CloseCycle cycle={cycle} />);
  await user.click(screen.getByRole("button", { name: "Đóng chu kỳ" }));
  const group = screen.getByRole("group", { name: "Xác nhận đóng chu kỳ" });
  await user.click(within(group).getByRole("button", { name: "Xác nhận đóng chu kỳ" }));
  await waitFor(() => expect(mocks.api.close).toHaveBeenCalledWith("c1", 3));
});
it("encodes the selected cycle in all workflow tab links", () => {
  mount(<EvaluationTabs employeeId="e1" cycleId="a&b" active="kpis" />);
  expect(screen.getByRole("link", { name: "Phản hồi 360" }).getAttribute("href")).toBe("/employees/e1/feedback?cycle_id=a%26b");
});
