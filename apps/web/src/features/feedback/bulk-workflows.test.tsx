// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiClientError } from "../../lib/api-client";
import { DetailContext } from "../workspace/detail-context";
import { FeedbackAdministration } from "./administration";
import { ReviewerMultiPicker } from "./reviewer-multi-picker";
import type { ReviewerOption } from "./api";

const mocks = vi.hoisted(() => ({ role: "HR", cycles: vi.fn(), participants: vi.fn(), api: { administration: vi.fn(), context: vi.fn(), options: vi.fn(), create: vi.fn(), createBatch: vi.fn() } }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { id: "hr", role: mocks.role } }) }));
vi.mock("../cycles/api", () => ({ reviewApi: { cycles: mocks.cycles, participants: mocks.participants } }));
vi.mock("./api", () => ({ feedbackApi: mocks.api }));
vi.mock("../organization/employee-form", () => ({ ReferencePicker: ({ value, onChange, labelOverride }: { value: string; onChange: (v: string) => void; labelOverride: string }) => <label>{labelOverride}<select value={value} onChange={(event) => onChange(event.target.value)}><option value="">Tất cả phòng ban</option><option value="d1">Kỹ thuật</option><option value="d2">Kinh doanh</option></select></label> }));
const option = (id: string): ReviewerOption => ({ reviewer_id: id, employee_id: `e-${id}`, employee_code: id.toUpperCase(), display_name: `Người ${id}`, is_active: true, existing_assignment_id: null, existing_status: null });
const page = <T,>(items: T[], total = items.length) => ({ items, total, page: 1, page_size: 20 });
const context = { participant_id: "p1", cycle_id: "c1", employee_id: "subject", employee_code: "NV01", display_name: "An", evidence_version: 3, cycle_status: "ACTIVE", finalized: false, active_assignment_count: 0, coverage: { ready: false, missing_relationships: ["SELF", "MANAGER"], pending_required: 0, blocked_required: 0 } };
function mount(child: ReactNode) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={cache}>{child}</QueryClientProvider>); return cache;
}
function Picker({ limit }: { limit?: number }) {
  const [selected, setSelected] = useState<ReviewerOption[]>([]);
  return <ReviewerMultiPicker participant="p1" relationship="PEER" value={selected} onChange={setSelected} limit={limit} />;
}
beforeEach(() => {
  vi.resetAllMocks(); mocks.role = "HR";
  mocks.cycles.mockResolvedValue(page([{ id: "c1", name: "Kỳ thử", status: "ACTIVE" }]));
  mocks.participants.mockResolvedValue(page([{ id: "p1", cycle_id: "c1", employee_id: "subject", employee_code: "NV01", display_name: "An", department_name: "Kỹ thuật" }]));
  mocks.api.administration.mockResolvedValue(page([])); mocks.api.context.mockResolvedValue(context);
  mocks.api.options.mockResolvedValue(page([option("one"), option("two")]));
  mocks.api.createBatch.mockResolvedValue({ assignment_ids: ["a1", "a2"], created_count: 2, evidence_version: 4 });
});

it("lets HR select a participant with no existing assignments directly from the workspace", async () => {
  const user = userEvent.setup(); mount(<FeedbackAdministration />);
  expect(await screen.findByRole("heading", { name: "Phân công phản hồi" })).toBeTruthy();
  await screen.findByRole("option", { name: "Kỳ thử" });
  await user.selectOptions(await screen.findByLabelText("Chu kỳ cần phân công"), "c1");
  await user.click(await screen.findByRole("button", { name: /NV01 · An/ }));
  expect(await screen.findByLabelText("Quan hệ người đánh giá")).toBeTruthy();
  expect(mocks.api.context).toHaveBeenCalledWith("p1");
  expect(mocks.api.create).not.toHaveBeenCalled(); expect(mocks.api.createBatch).not.toHaveBeenCalled();
});
it("opens participant assignment in the existing detail modal when workspace context is present", async () => {
  const open = vi.fn(), user = userEvent.setup();
  mount(<DetailContext.Provider value={{ open, close: vi.fn(), active: false }}><FeedbackAdministration /></DetailContext.Provider>);
  await screen.findByRole("option", { name: "Kỳ thử" });
  await user.selectOptions(await screen.findByLabelText("Chu kỳ cần phân công"), "c1");
  await user.click(await screen.findByRole("button", { name: /NV01 · An/ }));
  expect(open).toHaveBeenCalledWith({ kind: "administration", id: "p1", cycle: "c1", href: "/feedback-administration?participant_id=p1&cycle_id=c1" });
  expect(mocks.api.context).not.toHaveBeenCalled();
});
it("retains checked reviewers across pages and department filters and deduplicates select-all", async () => {
  mocks.api.options.mockImplementation((_p, _r, filters) => Promise.resolve(filters.page_size === 100 ? page([option("one"), option("two")]) : page([option(filters.page === 2 ? "two" : "one")], 21)));
  const user = userEvent.setup(); mount(<Picker />);
  await user.click(await screen.findByRole("checkbox", { name: "ONE · Người one" }));
  await user.click(screen.getByRole("button", { name: "Trang sau" }));
  await user.click(await screen.findByRole("checkbox", { name: "TWO · Người two" }));
  await user.selectOptions(screen.getByLabelText("Phòng ban người đánh giá"), "d1");
  await waitFor(() => expect(mocks.api.options).toHaveBeenLastCalledWith("p1", "PEER", expect.objectContaining({ page: 1, department_id: "d1", available_only: true })));
  expect(await screen.findByText(/Đã chọn 2\/100/)).toBeTruthy();
  // Narrow result is explicitly fetched in a single bounded request when selecting all.
  mocks.api.options.mockResolvedValue(page([option("one"), option("two")]));
  await user.selectOptions(screen.getByLabelText("Phòng ban người đánh giá"), "d2");
  await user.click(await screen.findByRole("button", { name: "Chọn toàn bộ kết quả lọc (2)" }));
  await waitFor(() => expect(mocks.api.options).toHaveBeenCalledWith("p1", "PEER", expect.objectContaining({ page_size: 100, department_id: "d2" })));
  expect(screen.getByText(/Đã chọn 2\/100/)).toBeTruthy();
});
it("requires a named confirmation before one atomic request for multiple reviewers", async () => {
  const user = userEvent.setup(); mount(<FeedbackAdministration participantId="p1" />);
  await user.selectOptions(await screen.findByLabelText("Quan hệ người đánh giá"), "PEER");
  await user.click(await screen.findByRole("checkbox", { name: "ONE · Người one" }));
  await user.click(screen.getByRole("checkbox", { name: "TWO · Người two" }));
  await user.click(screen.getByRole("button", { name: "Xem lại 2 người đã chọn" }));
  const preview = screen.getByRole("region", { name: "Xác nhận phân công hàng loạt" });
  expect(within(preview).getByText("ONE · Người one")).toBeTruthy();
  expect(within(preview).getByText("TWO · Người two")).toBeTruthy();
  expect(mocks.api.createBatch).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Xác nhận giao 2 phiếu" }));
  await waitFor(() => expect(mocks.api.createBatch).toHaveBeenCalledWith({ participant_id: "p1", reviewer_ids: ["one", "two"], relationship: "PEER", required: false, due_at: null, expected_evidence_version: 3 }, expect.anything()));
  expect(await screen.findByText(/Đã giao 2 phiếu/)).toBeTruthy();
  expect(mocks.api.create).not.toHaveBeenCalled();
});
it("keeps selection on stale errors and requires explicit reload and renewed confirmation", async () => {
  mocks.api.createBatch.mockRejectedValueOnce(new ApiClientError(409, "reviewer_ineligible", "changed", [{ reviewer_id: "two" }]));
  const user = userEvent.setup(), cache = mount(<FeedbackAdministration participantId="p1" />);
  await user.selectOptions(await screen.findByLabelText("Quan hệ người đánh giá"), "PEER");
  await user.click(await screen.findByRole("button", { name: "Chọn toàn bộ kết quả lọc (2)" }));
  await screen.findByText(/Đã chọn 2\/100/);
  act(() => { cache.setQueryData(["feedback", "administration", "context", "p1", "hr"], { ...context, evidence_version: 99 }); });
  await user.click(screen.getByRole("button", { name: "Xem lại 2 người đã chọn" }));
  await user.click(screen.getByRole("button", { name: "Xác nhận giao 2 phiếu" }));
  expect(await screen.findByText(/Người cần kiểm tra: TWO/)).toBeTruthy();
  expect(mocks.api.createBatch.mock.calls[0]![0].expected_evidence_version).toBe(3);
  expect(screen.getByRole("button", { name: "Xác nhận giao 2 phiếu" })).toHaveProperty("disabled", true);
  mocks.api.context.mockResolvedValue({ ...context, evidence_version: 5 });
  await user.click(screen.getByRole("button", { name: "Tải phiên bản mới, giữ nội dung" }));
  await waitFor(() => expect(screen.queryByRole("region", { name: "Xác nhận phân công hàng loạt" })).toBeNull());
  expect(screen.getByText(/Đã chọn 2\/100/)).toBeTruthy();
  expect(mocks.api.createBatch).toHaveBeenCalledTimes(1);
});
it("clears reviewer selection when changing the relationship", async () => {
  const user = userEvent.setup(); mount(<FeedbackAdministration participantId="p1" />);
  await user.selectOptions(await screen.findByLabelText("Quan hệ người đánh giá"), "PEER");
  await user.click(await screen.findByRole("checkbox", { name: "ONE · Người one" }));
  await user.selectOptions(screen.getByLabelText("Quan hệ người đánh giá"), "SUBORDINATE");
  expect(await screen.findByText(/Đã chọn 0\/100/)).toBeTruthy();
  expect(screen.getByRole("checkbox", { name: "ONE · Người one" })).toHaveProperty("checked", false);
});
it("respects remaining capacity and never interprets a page as the whole department", async () => {
  const user = userEvent.setup(); mount(<Picker limit={1} />);
  expect(await screen.findByRole("button", { name: "Chọn toàn bộ kết quả lọc (2)" })).toHaveProperty("disabled", true);
  await user.click(screen.getByRole("checkbox", { name: "ONE · Người one" }));
  expect(screen.getByRole("checkbox", { name: "TWO · Người two" })).toHaveProperty("disabled", true);
  expect(mocks.api.options.mock.calls.every((call) => call[2].page_size !== 100)).toBe(true);
});
it("keeps finalized participant administration read-only", async () => {
  mocks.api.context.mockResolvedValue({ ...context, finalized: true });
  mount(<FeedbackAdministration participantId="p1" />);
  expect(await screen.findByText(/Hồ sơ đã chốt hoặc kỳ đã đóng/)).toBeTruthy();
  expect(screen.queryByLabelText("Quan hệ người đánh giá")).toBeNull();
  expect(mocks.api.createBatch).not.toHaveBeenCalled();
});
