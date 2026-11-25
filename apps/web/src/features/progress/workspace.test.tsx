// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { Decision } from "./shared";
import { MeasurementEditor, ProgressWorkspace } from "./workspace";
import type { Checkin, Measurement, Metric, Metrics } from "./api";
import { CheckinDetail } from "./checkins";

const mocks = vi.hoisted(() => ({role: "EMPLOYEE", query: "", replace: vi.fn(), metrics: vi.fn(), measurements: vi.fn(), measurement: vi.fn(), checkins: vi.fn(), checkin: vi.fn(), snapshots: vi.fn(), snapshot: vi.fn(), coordination: vi.fn(), write: vi.fn(), participants: vi.fn(), items: vi.fn(), item: vi.fn(), plan: vi.fn()}));
vi.mock("../auth/auth-provider", () => ({useAuth: () => ({user: {id: "owner", role: mocks.role}})}));
vi.mock("next/navigation", () => ({useSearchParams: () => new URLSearchParams(mocks.query), useRouter: () => ({replace: mocks.replace})}));
vi.mock("./api", () => ({progressApi: mocks}));
vi.mock("../work-management/api", () => ({workApi: mocks}));
const page = <T,>(items: T[]) => ({items, total: items.length, page: 1, page_size: 20});
const goal: Metric = {goal_id: "goal", name: "Hồ sơ đã kiểm tra", method: "SUM", unit: "hồ sơ", target: "100", actual: null, data_status: "NO_DATA", source_count: 0, pending_count: 1, specification: {id: "goal", definition_id: "definition", baseline: "0", target: "100", weight: "100", method: "SUM", source: "Mỗi hồ sơ riêng biệt", acceptance: "QA xác nhận", numerator: null, denominator: null, milestones: [], definition: {code: "CASE", name: "Hồ sơ", direction: "HIGHER_IS_BETTER", unit: "hồ sơ"}}};
const metrics: Metrics = {plan_id: "plan", plan_version: 5, measurement_version: 0, employee_name: "Huy", owner_id: "owner", manager_id: "manager", can_submit: true, goals: [goal]};
const measurement: Measurement = {id: "measurement", plan_id: "plan", goal_id: "goal", version: 2, number: 1, source_key: "CASE-001", source_kind: "EXTERNAL_REFERENCE", work_item_id: null, occurred_at: "2026-11-25T08:00:00Z", milestone: null, status: "SUBMITTED", suspended: false, kind: "VALUE", payload: {value: "10", body: "QA xác nhận hồ sơ"}, method: "SUM", actions: ["verify", "return"], effective: null, is_correction: false, revisions: [], history: page([])};
function mount(content: ReactNode) {const cache = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}}); render(<QueryClientProvider client={cache}>{content}</QueryClientProvider>); return cache;}
beforeEach(() => {vi.resetAllMocks(); mocks.role = "EMPLOYEE"; mocks.query = ""; mocks.participants.mockResolvedValue(page([{plan_id: "plan", participant_id: "participant", employee_name: "Huy", cycle_name: "Tháng 12"}])); mocks.metrics.mockResolvedValue(metrics); mocks.measurements.mockResolvedValue(page([])); mocks.measurement.mockResolvedValue(measurement); mocks.checkins.mockResolvedValue(page([])); mocks.write.mockResolvedValue({...measurement, version: 3}); mocks.items.mockResolvedValue(page([]));});

it("lets the manager assign support after publication has locked preparation", async () => {
  mocks.role = "MANAGER";
  const meeting: Checkin = {id: "meeting", plan_id: "plan", version: 3, title: "Rà soát", status: "PUBLISHED",
    scheduled_at: "2026-11-25T08:00:00Z", verification_due_at: "2026-12-31T08:00:00Z", period_start: "2026-11-01", period_end: "2026-11-25",
    owner_id: "employee", manager_id: "owner", publication: 1, acknowledged_publication: 1, clarification_pending: false, snapshot_id: null,
    overdue: false, can_prepare: false, actions_open: true, actions: ["create_followup"], preparations: [], publications: [], followups: page([]), history: page([])};
  mocks.checkin.mockResolvedValue(meeting);
  const user = userEvent.setup(); mount(<CheckinDetail id="meeting" close={vi.fn()} />);
  await user.click(await screen.findByRole("tab", {name: "Hành động"}));
  await user.click(screen.getByRole("button", {name: "Giao hành động hỗ trợ"}));
  fireEvent.change(screen.getByLabelText("Đầu ra / hỗ trợ cần có"), {target: {value: "Xin dữ liệu QA đối tác"}});
  await user.click(screen.getByRole("button", {name: "Xem lại hành động hỗ trợ"}));
  await user.click(screen.getByRole("button", {name: "Giao và thông báo người nhận"}));
  await waitFor(() => expect(mocks.write).toHaveBeenCalledWith("checkins/meeting/follow-ups", expect.objectContaining({expected_version: 3, body: "Xin dữ liệu QA đối tác"})));
});

it("does not fetch private progress for ADMIN or HR", () => {
  mocks.role = "ADMIN"; mount(<ProgressWorkspace mode="measurements" />);
  expect(mocks.metrics).not.toHaveBeenCalled(); expect(mocks.participants).not.toHaveBeenCalled();
});

it("waits for the goal context before enabling a deep-linked measurement correction", async () => {
  mocks.query = "measurement=measurement";
  mocks.measurement.mockResolvedValue({...measurement, status: "VERIFIED", actions: ["draft"]});
  let resolveMetrics!: (value: Metrics) => void;
  mocks.metrics.mockImplementation(() => new Promise<Metrics>((resolve) => {resolveMetrics = resolve;}));
  const user = userEvent.setup(); mount(<ProgressWorkspace mode="measurements" />);
  const edit = await screen.findByRole("button", {name: "Sửa bản khai / đề nghị điều chỉnh"});
  expect((edit as HTMLButtonElement).disabled).toBe(true);
  await waitFor(() => expect(resolveMetrics).toBeTypeOf("function"));
  resolveMetrics(metrics);
  await waitFor(() => expect((edit as HTMLButtonElement).disabled).toBe(false));
  await user.click(edit);
  expect(await screen.findByLabelText("Bằng chứng và lý do thay đổi / rút số")).toBeTruthy();
});

it("distinguishes missing data from a verified zero without showing a score", async () => {
  mocks.metrics.mockResolvedValue({...metrics, goals: [goal, {...goal, goal_id: "zero", name: "Lỗi đã xác minh", actual: "0.0000", data_status: "VERIFIED", source_count: 1}]});
  mount(<ProgressWorkspace mode="measurements" />);
  await screen.findByText("Chưa đủ dữ liệu xác minh"); expect(screen.getByText("0.0000")).toBeTruthy();
  expect(screen.queryByText("Điểm hiệu suất")).toBeNull();
});

it("previews a delta and saves a draft with source and request UUID", async () => {
  const user = userEvent.setup(), dirty = vi.fn(), saved = vi.fn();
  mount(<MeasurementEditor metrics={metrics} goal={goal} dirty={dirty} saved={saved} />);
  fireEvent.change(screen.getByLabelText("Mã hồ sơ / sự kiện duy nhất"), {target: {value: "CASE-109"}});
  fireEvent.change(screen.getByLabelText(/Giá trị phát sinh riêng/), {target: {value: "10"}});
  fireEvent.change(screen.getByLabelText("Mô tả bằng chứng và cách đối chiếu"), {target: {value: "Đã kiểm tra mã hồ sơ"}});
  await user.click(screen.getByRole("button", {name: "Xem lại số đo"})); expect(mocks.write).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", {name: "Lưu bản khai"}));
  await waitFor(() => expect(mocks.write).toHaveBeenCalledWith("progress/goals/goal/measurements", expect.objectContaining({expected_version: 5, source_key: "CASE-109", value: "10", kind: "VALUE", client_request_id: expect.any(String)})));
  expect(saved).toHaveBeenCalled();
});

it("asks for numerator and denominator rather than a percent-only field", async () => {
  const user = userEvent.setup();
  const ratio = {...goal, method: "RATIO" as const, unit: "%", specification: {...goal.specification, method: "RATIO" as const, numerator: "Đúng hạn", denominator: "Đã xử lý"}};
  mount(<MeasurementEditor metrics={metrics} goal={ratio} dirty={vi.fn()} saved={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Mã hồ sơ / sự kiện duy nhất"), {target: {value: "AUDIT-12"}});
  fireEvent.change(screen.getByLabelText(/Tử số/), {target: {value: "9"}});
  fireEvent.change(screen.getByLabelText(/Mẫu số/), {target: {value: "10"}});
  fireEvent.change(screen.getByLabelText("Mô tả bằng chứng và cách đối chiếu"), {target: {value: "Đối chiếu nguồn"}});
  await user.click(screen.getByRole("button", {name: "Xem lại số đo"})); await user.click(screen.getByRole("button", {name: "Lưu bản khai"}));
  await waitFor(() => expect(mocks.write).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({numerator: "9", denominator: "10", value: null})));
});

it("retains a failed decision and reuses the same UUID when retrying unchanged content", async () => {
  mocks.write.mockRejectedValue(new Error("offline")); const user = userEvent.setup();
  mount(<Decision path="progress/measurements/measurement/actions" version={2} actions={["verify"]} dirty={vi.fn()} />);
  await user.type(screen.getByLabelText("Nhận xét / nội dung quyết định"), "Đã kiểm tra nguồn");
  await user.click(screen.getByRole("button", {name: "Xem lại trước khi gửi"})); await user.click(screen.getByRole("button", {name: "Xác nhận gửi"}));
  await screen.findByRole("alert"); expect((screen.getByLabelText("Nhận xét / nội dung quyết định") as HTMLTextAreaElement).value).toBe("Đã kiểm tra nguồn");
  await user.click(screen.getByRole("button", {name: "Xác nhận gửi"})); await waitFor(() => expect(mocks.write).toHaveBeenCalledTimes(2));
  expect(mocks.write.mock.calls[0]![1].client_request_id).toBe(mocks.write.mock.calls[1]![1].client_request_id);
});

it("keeps a decision draft across detail tabs and warns before closing", async () => {
  mocks.role = "MANAGER"; mocks.query = "measurement=measurement"; const user = userEvent.setup();
  mount(<ProgressWorkspace mode="measurements" />); const dialog = await screen.findByRole("dialog");
  const input = await within(dialog).findByLabelText("Nhận xét / nội dung quyết định"); await user.type(input, "Cần đối chiếu lần nữa");
  await user.click(within(dialog).getByRole("tab", {name: "Bằng chứng"})); await user.click(within(dialog).getByRole("tab", {name: "Nội dung"}));
  expect((input as HTMLTextAreaElement).value).toBe("Cần đối chiếu lần nữa");
  await user.click(within(dialog).getByRole("button", {name: "Đóng Chi tiết số đo KPI"})); await screen.findByText("Bạn có nội dung chưa lưu. Đóng sẽ bỏ bản nhập.");
});

it("preserves an unsaved private preparation when the manager publishes during typing", async () => {
  const meeting = {id: "meeting", plan_id: "plan", version: 1, title: "Rà soát tuần", status: "OPEN",
    scheduled_at: "2026-11-26T08:00:00Z", period_start: "2026-11-25", period_end: "2026-11-25",
    publication: 0, acknowledged_publication: null, clarification_pending: false, owner_id: "owner",
    manager_id: "manager", verification_due_at: "2026-12-31T08:00:00Z", snapshot_id: null,
    overdue: false, can_prepare: true, actions: [], preparations: [], publications: [], followups: page([]), history: page([])};
  mocks.checkin.mockResolvedValue(meeting);
  const user = userEvent.setup();
  const cache = mount(<CheckinDetail id="meeting" close={vi.fn()} />);
  const input = await screen.findByLabelText("Nội dung chuẩn bị");
  await user.type(input, "Cần hỗ trợ dữ liệu, tôi chưa lưu bản này");
  mocks.checkin.mockResolvedValue({...meeting, version: 2, status: "PUBLISHED", publication: 1, can_prepare: false});
  await cache.invalidateQueries({queryKey: ["checkins"]});
  await screen.findByText(/Phần chuẩn bị đã khóa/);
  expect((screen.getByLabelText("Nội dung chuẩn bị") as HTMLTextAreaElement).value).toBe("Cần hỗ trợ dữ liệu, tôi chưa lưu bản này");
  expect((screen.getByLabelText("Nội dung chuẩn bị") as HTMLTextAreaElement).readOnly).toBe(true);
  expect(mocks.write).not.toHaveBeenCalled();
});
