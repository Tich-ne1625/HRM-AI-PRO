// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiClientError } from "../../lib/api-client";
import { KpiCatalog } from "../kpis/catalog";
import { AllocationEditor, EmployeeKpis } from "../kpis/employee-kpis";
import { ScoringSettings } from "../settings/scoring-settings";
import type { Allocation, Cycle, Definition } from "./api";
import { CycleDetail } from "./cycle-detail";
import { CycleDirectory } from "./cycle-directory";
import { decimalUnits } from "./shared";

const mocks = vi.hoisted(() => ({role: "HR", employees: vi.fn(), api: {
  cycles: vi.fn(), cycle: vi.fn(), saveCycle: vi.fn(), participants: vi.fn(), enroll: vi.fn(), remove: vi.fn(), activate: vi.fn(),
  definitions: vi.fn(), saveDefinition: vi.fn(), options: vi.fn(), allocation: vi.fn(), replace: vi.fn(), actual: vi.fn(), defaults: vi.fn(), saveDefaults: vi.fn(),
}}));
vi.mock("../auth/auth-provider", () => ({useAuth: () => ({user: {role: mocks.role}})}));
vi.mock("./api", () => ({reviewApi: mocks.api}));
vi.mock("../organization/api", async (original) => ({...await original<typeof import("../organization/api")>(), organizationApi: {employees: mocks.employees}}));
const policy = {schema_version: 1 as const, kpi_weight: "70.00", feedback_weight: "30.00", kpi_cap: "100.00"};
const cycle: Cycle = {id: "cycle", name: "Quý IV", start_date: "2026-10-01", end_date: "2026-12-31", status: "DRAFT", version: 2, policy, policy_source_version: 1, policy_is_preview: true, participant_count: 1, can_edit: true, can_activate: true, activated_at: null};
const definition: Definition = {id: "sales", code: "SALES", name: "Doanh số", unit: "VND", description: "", direction: "HIGHER_IS_BETTER", version: 1, is_active: true};
const participant = {id: "participant", cycle_id: "cycle", employee_id: "alice", employee_code: "NV01", display_name: "An", department_id: "dept", department_name: "Kỹ thuật", position_title: "Kỹ sư", evidence_version: 3, is_snapshot: true, can_manage_kpis: true};
const allocation: Allocation = {participant, cycle_status: "ACTIVE", items: [{id: "assigned", definition_id: "sales", definition: {...definition, schema_version: 1}, target: "100.0000", weight: "100.00", actual: null}]};
const page = <T,>(items: T[], total = items.length) => ({items, total, page: 1, page_size: 20});
function mount(child: ReactNode) {
  const cache = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}});
  render(<QueryClientProvider client={cache}>{child}</QueryClientProvider>);
  return cache;
}
beforeEach(() => {
  vi.resetAllMocks(); mocks.role = "HR";
  mocks.api.cycles.mockResolvedValue(page([cycle])); mocks.api.cycle.mockResolvedValue(cycle);
  mocks.api.participants.mockResolvedValue(page([participant])); mocks.employees.mockResolvedValue(page([]));
  mocks.api.definitions.mockResolvedValue(page([definition])); mocks.api.options.mockResolvedValue(page([definition]));
  mocks.api.allocation.mockResolvedValue(allocation); mocks.api.defaults.mockResolvedValue({version: 1, policy});
  mocks.api.saveCycle.mockResolvedValue({...cycle, version: 3}); mocks.api.activate.mockResolvedValue({...cycle, status: "ACTIVE"});
  mocks.api.enroll.mockResolvedValue({version: 3, count: 1}); mocks.api.saveDefinition.mockResolvedValue(definition);
  mocks.api.replace.mockResolvedValue(allocation); mocks.api.actual.mockResolvedValue(allocation); mocks.api.saveDefaults.mockResolvedValue({version: 2, policy});
});

it("parses percentage units exactly and rejects excess precision", () => {
  expect(decimalUnits("33.33", 2, 3)! + decimalUnits("66.67", 2, 3)!).toBe(10000);
  for (const value of ["1.001", "NaN", "Infinity", "1e2", "-1", " 1.0"]) expect(decimalUnits(value, 2, 3)).toBeNull();
});
it("lets HR create a dated draft and refreshes the list", async () => {
  const user = userEvent.setup(); mount(<CycleDirectory />);
  await screen.findByRole("link", {name: "Quý IV"});
  await user.type(screen.getByLabelText("Tên chu kỳ"), "Quý I");
  fireEvent.change(screen.getByLabelText("Ngày bắt đầu"), {target: {value: "2027-01-01"}});
  fireEvent.change(screen.getByLabelText("Ngày kết thúc"), {target: {value: "2027-03-31"}});
  await user.click(screen.getByRole("button", {name: "Tạo chu kỳ nháp"}));
  await waitFor(() => expect(mocks.api.saveCycle).toHaveBeenCalledWith(null, {name: "Quý I", start_date: "2027-01-01", end_date: "2027-03-31"}));
  await waitFor(() => expect(mocks.api.cycles.mock.calls.length).toBeGreaterThan(1));
});
it("keeps cycle input after a failed save", async () => {
  mocks.api.saveCycle.mockRejectedValue(new Error("offline")); const user = userEvent.setup(); mount(<CycleDetail id="cycle" />);
  const input = await screen.findByLabelText("Tên chu kỳ"); await user.clear(input); await user.type(input, "Chưa lưu");
  await user.click(screen.getByRole("button", {name: "Lưu thông tin chu kỳ"}));
  await screen.findByRole("alert"); expect((input as HTMLInputElement).value).toBe("Chưa lưu");
});
it("does not fetch domain data or show HR forms to ADMIN", () => {
  mocks.role = "ADMIN"; mount(<CycleDirectory />); expect(mocks.api.cycles).not.toHaveBeenCalled(); expect(screen.getByRole("alert").textContent).toContain("không có quyền");
});
it("shows managers a read-only cycle directory", async () => {
  mocks.role = "MANAGER"; mount(<CycleDirectory />); await screen.findByRole("link", {name: "Quý IV"}); expect(screen.queryByLabelText("Tên chu kỳ")).toBeNull();
});
it("requires explicit activation confirmation and shows actionable failures", async () => {
  mocks.api.activate.mockRejectedValue(new ApiClientError(409, "activation_requirements_not_met", "Requirements", [{employee_id: "alice", code: "self_account_required"}]));
  const user = userEvent.setup(); mount(<CycleDetail id="cycle" />);
  await user.click(await screen.findByRole("button", {name: "Kích hoạt chu kỳ"})); expect(mocks.api.activate).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", {name: "Xác nhận kích hoạt"}));
  await screen.findByText(/Nhân viên cần tài khoản đang hoạt động\./); expect(screen.getByRole("link", {name: "Hồ sơ cần kiểm tra"}).getAttribute("href")).toBe("/employees/alice");
  expect(mocks.api.activate).toHaveBeenCalledWith("cycle", 2);
});
it("retains employee selection across enrollment pages", async () => {
  mocks.employees.mockImplementation(({page: p}) => Promise.resolve(page([{id: p === 1 ? "e1" : "e2", employee_code: p === 1 ? "NV1" : "NV2", display_name: p === 1 ? "Một" : "Hai"}], 21)));
  const user = userEvent.setup(); mount(<CycleDetail id="cycle" />);
  await user.click(await screen.findByRole("checkbox", {name: "NV1 · Một"}));
  const next = screen.getAllByRole("button", {name: "Trang sau"})[0]!; await user.click(next);
  await user.click(await screen.findByRole("checkbox", {name: "NV2 · Hai"}));
  await user.click(screen.getByRole("button", {name: "Thêm người đã chọn"}));
  await waitFor(() => expect(mocks.api.enroll).toHaveBeenCalledWith("cycle", 2, ["e1", "e2"]));
});
it("HR creates a KPI and confirms retirement separately", async () => {
  const user = userEvent.setup(); mount(<KpiCatalog />); await screen.findByText("SALES · Doanh số");
  await user.type(screen.getByLabelText("Mã KPI"), "quality"); await user.type(screen.getByLabelText("Tên KPI"), "Chất lượng"); await user.type(screen.getByLabelText("Đơn vị"), "%");
  await user.click(screen.getByRole("button", {name: "Thêm định nghĩa"}));
  await waitFor(() => expect(mocks.api.saveDefinition).toHaveBeenCalledWith(null, {code: "QUALITY", name: "Chất lượng", unit: "%", direction: "HIGHER_IS_BETTER", description: ""}));
  await user.click(screen.getByRole("button", {name: "Ngừng sử dụng SALES"})); expect(mocks.api.saveDefinition).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole("button", {name: "Xác nhận ngừng KPI"})); await waitFor(() => expect(mocks.api.saveDefinition).toHaveBeenLastCalledWith("sales", {expected_version: 1, is_active: false}));
});
it("keeps KPI definition input after a failed save", async () => {
  mocks.api.saveDefinition.mockRejectedValue(new Error("offline")); const user = userEvent.setup(); mount(<KpiCatalog />);
  await user.type(await screen.findByLabelText("Mã KPI"), "quality"); await user.type(screen.getByLabelText("Tên KPI"), "Chất lượng"); await user.type(screen.getByLabelText("Đơn vị"), "%"); await user.click(screen.getByRole("button", {name: "Thêm định nghĩa"}));
  await screen.findByRole("alert"); expect((screen.getByLabelText("Tên KPI") as HTMLInputElement).value).toBe("Chất lượng");
});
it("blocks incomplete weights and sends the complete allocation with its captured version", async () => {
  const onSave = vi.fn(), user = userEvent.setup(); mount(<AllocationEditor initial={allocation} employee="alice" cycle="cycle" pending={false} onSave={onSave} />);
  const weight = screen.getByLabelText("Trọng số SALES · Doanh số (%)"); await user.clear(weight); await user.type(weight, "99.99");
  expect((screen.getByRole("button", {name: "Lưu toàn bộ phân bổ"}) as HTMLButtonElement).disabled).toBe(true);
  await user.clear(weight); await user.type(weight, "100.00"); await user.click(screen.getByRole("button", {name: "Lưu toàn bộ phân bổ"}));
  await waitFor(() => expect(onSave).toHaveBeenCalledWith(3, [{definition_id: "sales", target: "100.0000", weight: "100.00"}]));
});
it("requires confirmation before a target change clears existing actuals", async () => {
  const onSave = vi.fn(), user = userEvent.setup(); mount(<AllocationEditor initial={{...allocation, items: [{...allocation.items[0]!, actual: "50.0000"}]}} employee="alice" cycle="cycle" pending={false} onSave={onSave} />);
  const target = screen.getByLabelText("Mục tiêu SALES · Doanh số (VND)"); await user.clear(target); await user.type(target, "200.0000"); await user.click(screen.getByRole("button", {name: "Lưu toàn bộ phân bổ"})); expect(onSave).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", {name: "Xác nhận lưu và xóa thực tế liên quan"})); await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
});
it("retains allocation edits after a stale conflict and never retries automatically", async () => {
  mocks.api.replace.mockRejectedValue(new ApiClientError(409, "stale_evidence_version", "Stale")); const user = userEvent.setup(); mount(<EmployeeKpis id="alice" cycle="cycle" />);
  await user.click(await screen.findByRole("button", {name: "Chỉnh phân bổ KPI"}));
  const input = screen.getByLabelText("Mục tiêu SALES · Doanh số (VND)"); await user.clear(input); await user.type(input, "150.0000");
  await user.click(screen.getByRole("button", {name: "Lưu toàn bộ phân bổ"})); await screen.findByRole("alert"); expect((input as HTMLInputElement).value).toBe("150.0000"); expect(mocks.api.replace).toHaveBeenCalledTimes(1);
});
it("distinguishes zero actual from missing and saves with the displayed evidence version", async () => {
  const user = userEvent.setup(); mount(<EmployeeKpis id="alice" cycle="cycle" />);
  expect(await screen.findByText("Chưa nhập")).toBeTruthy(); await user.click(screen.getByRole("button", {name: "Nhập thực tế SALES"}));
  await user.type(screen.getByLabelText("Thực tế SALES"), "0.0000"); await user.click(screen.getByRole("button", {name: "Lưu thực tế SALES"}));
  await waitFor(() => expect(mocks.api.actual).toHaveBeenCalledWith("assigned", 3, "0.0000"));
});
it("renders employee KPI read-only and does not fetch allocation options", async () => {
  mocks.role = "EMPLOYEE"; mocks.api.allocation.mockResolvedValue({...allocation, participant: {...participant, can_manage_kpis: false}}); mount(<EmployeeKpis id="alice" cycle="cycle" />);
  await screen.findByText("Chưa nhập"); expect(screen.queryByRole("button", {name: "Chỉnh phân bổ KPI"})).toBeNull(); expect(mocks.api.options).not.toHaveBeenCalled();
});
it("does not silently adopt a background evidence version while actual input is open", async () => {
  const user = userEvent.setup(), cache = mount(<EmployeeKpis id="alice" cycle="cycle" />);
  await user.click(await screen.findByRole("button", {name: "Nhập thực tế SALES"}));
  await user.type(screen.getByLabelText("Thực tế SALES"), "25.0000");
  act(() => {cache.setQueryData(["reviews", "allocation", "alice", "cycle"], {...allocation, participant: {...participant, evidence_version: 4}});});
  await user.click(screen.getByRole("button", {name: "Lưu thực tế SALES"}));
  await waitFor(() => expect(mocks.api.actual).toHaveBeenCalledWith("assigned", 3, "25.0000"));
});
it("requires an explicit cycle selection before fetching employee KPIs", () => {
  mount(<EmployeeKpis id="alice" cycle="" />); expect(mocks.api.allocation).not.toHaveBeenCalled(); expect(screen.getByRole("link", {name: "Chọn chu kỳ đánh giá"})).toBeTruthy();
});
it("ADMIN saves defaults while HR cannot fetch them", async () => {
  mocks.role = "ADMIN"; const user = userEvent.setup(); mount(<ScoringSettings />);
  const cap = await screen.findByLabelText("Giới hạn điểm KPI"); await user.clear(cap); await user.type(cap, "150.00"); await user.click(screen.getByRole("button", {name: "Lưu cấu hình"}));
  await waitFor(() => expect(mocks.api.saveDefaults).toHaveBeenCalledWith(1, {...policy, kpi_cap: "150.00"}));
});
it("rejects defaults whose component weights do not total 100", async () => {
  mocks.role = "ADMIN"; const user = userEvent.setup(); mount(<ScoringSettings />);
  const weight = await screen.findByLabelText("Trọng số KPI (%)"); await user.clear(weight); await user.type(weight, "50.00"); await user.click(screen.getByRole("button", {name: "Lưu cấu hình"})); await screen.findByRole("alert"); expect(mocks.api.saveDefaults).not.toHaveBeenCalled();
});
it("does not request system defaults for HR", () => {
  mount(<ScoringSettings />); expect(mocks.api.defaults).not.toHaveBeenCalled(); expect(screen.getByRole("alert").textContent).toContain("ADMIN");
});
