// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiClientError } from "../../lib/api-client";
import { navigationGroups, workspaceRouteAllowed } from "../workspace/navigation-model";
import { WorkWorkspace } from "./workspace";
import type { Plan, Work } from "./api";

const mocks = vi.hoisted(() => ({role: "EMPLOYEE", query: "", replace: vi.fn(), participants: vi.fn(), items: vi.fn(), item: vi.fn(), plan: vi.fn(), history: vi.fn(), write: vi.fn(), definitions: vi.fn()}));
vi.mock("../auth/auth-provider", () => ({useAuth: () => ({user: {id: "user", role: mocks.role}})}));
vi.mock("next/navigation", () => ({useSearchParams: () => new URLSearchParams(mocks.query), useRouter: () => ({replace: mocks.replace})}));
vi.mock("./api", async (original) => ({...await original<typeof import("./api")>(), workApi: mocks}));
const page = <T,>(items: T[]) => ({items, total: items.length, page: 1, page_size: 20});
const plan: Plan = {id: "plan", participant_id: "participant", version: 1, revision: 1, status: "APPROVED", acknowledged_revision: null, objective: "Hỗ trợ khách hàng", employee_name: "Huy", cycle_id: "cycle", cycle_name: "Tháng 12", cycle_status: "DRAFT", start_date: "2026-12-01", end_date: "2026-12-31", goals: [], actions: ["acknowledge", "clarify", "comment"], can_create_work: false, is_manager: false, needs_hr: false, schedule: {}};
const work: Work = {id: "work", plan_id: "plan", version: 1, title: "Kiểm tra hồ sơ", acceptance: "QA xác nhận", priority: "NORMAL", source_key: "CSKH-1", due_at: "2026-12-01T08:00:00Z", status: "IN_PROGRESS", goal_id: null, blocked: false, blocked_reason: "", employee_name: "Huy", cycle_name: "Tháng 12", actions: ["submit", "block", "comment", "request_change"], needs_hr: false, next_actor: "Nhân viên", submissions: [], submission_total: 0};
function mount() {const cache = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}}); render(<QueryClientProvider client={cache}><WorkWorkspace /></QueryClientProvider>); return cache;}
beforeEach(() => {vi.resetAllMocks(); mocks.role = "EMPLOYEE"; mocks.query = ""; mocks.participants.mockResolvedValue(page([])); mocks.items.mockResolvedValue(page([work])); mocks.item.mockResolvedValue(work); mocks.plan.mockResolvedValue(plan); mocks.history.mockResolvedValue(page([])); mocks.definitions.mockResolvedValue(page([])); mocks.write.mockResolvedValue({...work, version: 2});});

it("does not load work data for ADMIN and keeps role navigation clean", () => {
  mocks.role = "ADMIN"; mount(); expect(screen.getByRole("alert").textContent).toContain("không có quyền"); expect(mocks.items).not.toHaveBeenCalled(); expect(mocks.participants).not.toHaveBeenCalled();
  expect(navigationGroups("ADMIN").some((g) => g.href === "/work-management")).toBe(false);
  expect(navigationGroups("HR").some((g) => g.href === "/work-management")).toBe(false);
  expect(workspaceRouteAllowed("ADMIN", "/work-management")).toBe(false);
});
it("HR sees plan coordination without querying individual work", async () => {
  mocks.role = "HR"; mount(); await screen.findByText("Chưa có kỳ quản lý công việc"); expect(mocks.items).not.toHaveBeenCalled(); expect(screen.queryByRole("button", {name: "Công việc"})).toBeNull();
});
it("preserves filters when opening and closing a work dialog", async () => {
  const user = userEvent.setup(); mount(); await screen.findByText("Kiểm tra hồ sơ"); await user.selectOptions(screen.getByLabelText("Trạng thái"), "IN_PROGRESS");
  await user.click(screen.getByRole("button", {name: "Mở công việc"})); await screen.findByRole("dialog"); await user.click(screen.getByRole("button", {name: "Đóng Chi tiết công việc"}));
  expect((screen.getByLabelText("Trạng thái") as HTMLSelectElement).value).toBe("IN_PROGRESS");
});
it("opens a notification target and keeps evidence draft across tabs and errors", async () => {
  mocks.query = "item=work"; mocks.write.mockRejectedValue(new ApiClientError(409, "stale_version", "Changed")); const user = userEvent.setup(); mount();
  const dialog = await screen.findByRole("dialog"); await user.click(await within(dialog).findByRole("tab", {name: "Tiến trình & bằng chứng"}));
  const input = within(dialog).getByLabelText("Bằng chứng và kết quả thực hiện"); await user.type(input, "Đã có xác nhận QA");
  await user.click(within(dialog).getByRole("tab", {name: "Lịch sử"})); await user.click(within(dialog).getByRole("tab", {name: "Tiến trình & bằng chứng"})); expect((input as HTMLTextAreaElement).value).toBe("Đã có xác nhận QA");
  const panel = within(dialog).getByRole("tabpanel", {name: "Tiến trình & bằng chứng"}); await user.click(within(panel).getByRole("button", {name: "Xem lại trước khi gửi"})); await user.click(within(panel).getByRole("button", {name: "Xác nhận gửi"}));
  await screen.findByText(/Dữ liệu vừa thay đổi/); expect((input as HTMLTextAreaElement).value).toBe("Đã có xác nhận QA");
  await user.click(within(dialog).getByRole("button", {name: "Đóng Chi tiết công việc"})); expect(screen.getByText(/Bạn có nội dung chưa lưu/)).toBeTruthy(); await user.click(screen.getByRole("button", {name: "Tiếp tục chỉnh sửa"})); expect(screen.getByRole("dialog")).toBeTruthy();
});
it("requires explicit acknowledgement of the displayed plan revision", async () => {
  mocks.query = "plan=plan"; const user = userEvent.setup(); mount(); const dialog = await screen.findByRole("dialog"); await screen.findByText("Hỗ trợ khách hàng");
  const panel = within(dialog).getByRole("tabpanel", {name: "Nội dung"}); await user.click(within(panel).getByRole("button", {name: "Xem lại trước khi gửi"})); expect(mocks.write).not.toHaveBeenCalled(); await user.click(within(panel).getByRole("button", {name: "Xác nhận gửi"}));
  await waitFor(() => expect(mocks.write).toHaveBeenCalledWith("plans/plan/actions", expect.objectContaining({action: "acknowledge", revision: 1, expected_version: 1, client_request_id: expect.any(String)})));
});
it("navigates detail tabs with arrow keys", async () => {
  mocks.query = "item=work"; mount(); const content = await screen.findByRole("tab", {name: "Nội dung"}); content.focus(); fireEvent.keyDown(content, {key: "ArrowRight"}); expect(document.activeElement?.textContent).toBe("Tiến trình & bằng chứng"); expect(screen.getByRole("tab", {name: "Tiến trình & bằng chứng"}).getAttribute("aria-selected")).toBe("true");
});

it("manager reviews plan weights before saving and retains draft after a failure", async () => {
  mocks.role = "MANAGER";
  mocks.participants.mockResolvedValue(page([{participant_id: "participant", employee_name: "Huy", cycle_id: "cycle", cycle_name: "Tháng 12", cycle_status: "DRAFT", plan_id: null, plan_status: null, acknowledged: false, can_draft: true, needs_hr: false}]));
  mocks.definitions.mockResolvedValue(page([{id: "kpi", code: "CASE", name: "Hồ sơ", unit: "hồ sơ", description: "", direction: "HIGHER_IS_BETTER", version: 1, is_active: true}]));
  mocks.write.mockRejectedValue(new Error("offline"));
  const user = userEvent.setup(); mount(); await user.click(screen.getByRole("button", {name: "Kế hoạch & mục tiêu"})); await user.click(await screen.findByRole("button", {name: "Lập kế hoạch"}));
  await user.type(screen.getByLabelText("Mục tiêu chung"), "Hỗ trợ khách hàng có xác minh"); await user.selectOptions(screen.getByLabelText("KPI"), "kpi");
  await user.type(screen.getByLabelText("Mục tiêu cần đạt"), "120"); await user.type(screen.getByLabelText("Trọng số (%)"), "50"); await user.type(screen.getByLabelText("Nguồn số liệu / mã hồ sơ đối chiếu"), "Mã CSKH duy nhất"); await user.type(screen.getByLabelText("Tiêu chuẩn nghiệm thu"), "QA xác nhận");
  await user.click(screen.getByRole("button", {name: "Xem lại kế hoạch"})); expect(await screen.findByRole("alert")).toBeTruthy(); expect(mocks.write).not.toHaveBeenCalled();
  await user.clear(screen.getByLabelText("Trọng số (%)")); await user.type(screen.getByLabelText("Trọng số (%)"), "100"); await user.click(screen.getByRole("button", {name: "Xem lại kế hoạch"})); expect(mocks.write).not.toHaveBeenCalled(); await user.click(screen.getByRole("button", {name: "Lưu bản kế hoạch"})); await screen.findByText(/Chưa kết nối được máy chủ/); expect((screen.getByLabelText("Mục tiêu chung") as HTMLTextAreaElement).value).toContain("Hỗ trợ khách hàng");
}, 15000);

it("edits the employee proposal before publication with its original version", async () => {
  mocks.query = "item=work";
  mocks.item.mockResolvedValue({...work, status: "PROPOSED", actions: ["edit_proposal", "comment"]});
  mocks.plan.mockResolvedValue({...plan, cycle_status: "ACTIVE", acknowledged_revision: 1});
  const user = userEvent.setup(); mount(); await user.click(await screen.findByRole("button", {name: "Chỉnh sửa đề xuất"}));
  const title = await screen.findByLabelText("Tên công việc");
  expect((title as HTMLInputElement).value).toBe("Kiểm tra hồ sơ");
  fireEvent.change(title, {target: {value: "Đề xuất đã làm rõ"}});
  await user.click(screen.getByRole("button", {name: "Xem lại công việc"}));
  expect(mocks.write).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", {name: "Xác nhận lưu đề xuất"}));
  await waitFor(() => expect(mocks.write).toHaveBeenCalledWith("items/work/draft", expect.objectContaining({title: "Đề xuất đã làm rõ", expected_version: 1})));
});
