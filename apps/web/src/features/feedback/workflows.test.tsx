// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiClientError } from "../../lib/api-client";
import { FeedbackAdministration } from "./administration";
import { FeedbackDetail } from "./detail";
import { FeedbackInbox } from "./inbox";
import { FeedbackSummary } from "./summary";

const mocks = vi.hoisted(() => ({ role: "EMPLOYEE", api: {
  list: vi.fn(), administration: vi.fn(), context: vi.fn(), adminDetail: vi.fn(), detail: vi.fn(), submit: vi.fn(), summary: vi.fn(), coverage: vi.fn(),
  options: vi.fn(), create: vi.fn(), update: vi.fn(), cancel: vi.fn(), replace: vi.fn(),
} }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { id: "user", role: mocks.role } }) }));
vi.mock("./api", () => ({ feedbackApi: mocks.api }));
const assignment = {
  id: "a1", participant_id: "p1", cycle_id: "c1", cycle_name: "Quý IV", cycle_status: "ACTIVE",
  start_date: "2026-10-01", end_date: "2026-12-31", employee_id: "e1", employee_code: "NV01",
  display_name: "An", relationship: "SELF", required: true, status: "OPEN", due_at: null,
  version: 1, evidence_version: 3, finalized: false, submission: null,
};
function mount(child: ReactNode) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={cache}>{child}</QueryClientProvider>);
  return cache;
}
beforeEach(() => {
  vi.resetAllMocks(); mocks.role = "EMPLOYEE";
  mocks.api.list.mockResolvedValue({ items: [assignment], total: 1, page: 1, page_size: 20 });
  mocks.api.detail.mockResolvedValue(assignment);
  mocks.api.administration.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  mocks.api.context.mockResolvedValue({ participant_id: "p1", cycle_id: "c1", employee_id: "e1", employee_code: "NV01", display_name: "An", evidence_version: 3, cycle_status: "ACTIVE", finalized: false,
    coverage: { ready: false, missing_relationships: ["SELF", "MANAGER"], pending_required: 0, blocked_required: 0 } });
  mocks.api.options.mockResolvedValue({ items: [{ reviewer_id: "user", employee_id: "e1", employee_code: "NV01", display_name: "An", is_active: true, existing_assignment_id: null, existing_status: null }], total: 1, page: 1, page_size: 20 });
  mocks.api.create.mockResolvedValue(assignment);
  mocks.api.submit.mockResolvedValue({ ...assignment, status: "SUBMITTED", version: 2, evidence_version: 4,
    submission: { rating: 4, comment: "Cẩn thận", submitted_at: "2026-10-20T00:00:00Z" } });
});
it("allows an ADMIN reviewer to open their own inbox", async () => {
  mocks.role = "ADMIN"; mount(<FeedbackInbox />);
  expect(await screen.findByRole("link", { name: /NV01/ })).toHaveProperty("href", expect.stringContaining("/feedback/a1"));
  expect(mocks.api.list).toHaveBeenCalledWith(expect.objectContaining({ view: "mine" }));
});
it("prevents non-HR administration from fetching raw data", () => {
  mount(<FeedbackAdministration participantId="p1" />);
  expect(screen.getByRole("alert").textContent).toContain("HR");
  expect(mocks.api.list).not.toHaveBeenCalled();
});
it("requires confirmation and sends only captured versions and plain feedback", async () => {
  const user = userEvent.setup(); mount(<FeedbackDetail id="a1" />);
  await user.selectOptions(await screen.findByLabelText("Mức đánh giá"), "4");
  await user.type(screen.getByLabelText("Nhận xét"), "Cẩn thận");
  await user.click(screen.getByRole("button", { name: "Kiểm tra và gửi" }));
  expect(mocks.api.submit).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Xác nhận gửi một lần" }));
  await waitFor(() => expect(mocks.api.submit).toHaveBeenCalledWith({ assignment_id: "a1",
    expected_assignment_version: 1, expected_evidence_version: 3, rating: 4, comment: "Cẩn thận" }));
  await screen.findByText("Phản hồi đã được ghi nhận.");
  expect(screen.queryByLabelText("Nhận xét")).toBeNull();
});
it("keeps text on conflict and updates versions only after explicit reload", async () => {
  mocks.api.submit.mockRejectedValue(new ApiClientError(409, "stale_evidence_version", "stale"));
  const user = userEvent.setup(), cache = mount(<FeedbackDetail id="a1" />);
  await user.type(await screen.findByLabelText("Nhận xét"), "Bản nháp giữ lại");
  await user.selectOptions(screen.getByLabelText("Mức đánh giá"), "4");
  act(() => { cache.setQueryData(["feedback", "mine", "detail", "a1", "user"], { ...assignment, evidence_version: 99 }); });
  await user.click(screen.getByRole("button", { name: "Kiểm tra và gửi" }));
  await user.click(screen.getByRole("button", { name: "Xác nhận gửi một lần" }));
  await screen.findByRole("alert");
  expect(mocks.api.submit.mock.calls[0]![0].expected_evidence_version).toBe(3);
  expect((screen.getByLabelText("Nhận xét") as HTMLTextAreaElement).value).toBe("Bản nháp giữ lại");
  mocks.api.detail.mockResolvedValue({ ...assignment, evidence_version: 5 });
  await user.click(screen.getByRole("button", { name: "Tải phiên bản mới, giữ nội dung" }));
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect((screen.getByLabelText("Nhận xét") as HTMLTextAreaElement).value).toBe("Bản nháp giữ lại");
});
it("does not offer submission when expired, cancelled or finalized", async () => {
  mocks.api.detail.mockResolvedValue({ ...assignment, due_at: "2020-01-01T00:00:00Z" });
  mount(<FeedbackDetail id="a1" />);
  await screen.findByText(/Đã quá hạn/);
  expect(screen.queryByRole("button", { name: "Kiểm tra và gửi" })).toBeNull();
});
it("renders a submitted comment as text with no HTML execution", async () => {
  mocks.api.detail.mockResolvedValue({ ...assignment, status: "SUBMITTED", submission: { rating: 5,
    comment: "<script>alert(1)</script>", submitted_at: "2026-10-20T00:00:00Z" } });
  mount(<FeedbackDetail id="a1" />);
  await screen.findByText("<script>alert(1)</script>");
  expect(document.querySelector("script")).toBeNull();
});
it("explains suppressed groups without disclosing their counts", async () => {
  mocks.api.summary.mockResolvedValue({ participant_id: "p1", employee_id: "e1", cycle_id: "c1",
    evidence_version: 3, ready: false, count: 1, mean: "4.00", own_submission: null,
    groups: [{ relationship: "PEER", suppressed: true, count: null, mean: null }] });
  mount(<FeedbackSummary employeeId="e1" cycleId="c1" />);
  await screen.findByText(/Chưa đủ ba người/);
  expect(mocks.api.list).not.toHaveBeenCalled();
});
it("HR assigns mandatory self through the eligible picker and captured evidence version", async () => {
  mocks.role = "HR"; const user = userEvent.setup(); mount(<FeedbackAdministration participantId="p1" />);
  await screen.findByRole("option", { name: "NV01 · An" });
  await user.selectOptions(screen.getByLabelText("Người đánh giá hợp lệ"), "user");
  await user.click(screen.getByRole("button", { name: "Giao phản hồi" }));
  await waitFor(() => expect(mocks.api.create).toHaveBeenCalledWith({ participant_id: "p1", reviewer_id: "user", relationship: "SELF", required: true, due_at: null, expected_evidence_version: 3 }));
});
it("HR cannot select a disabled historical account or create a cancelled duplicate", async () => {
  mocks.role = "HR";
  mocks.api.options.mockResolvedValue({ items: [{ reviewer_id: "user", employee_id: "e1", employee_code: "NV01", display_name: "An", is_active: false, existing_assignment_id: "cancelled", existing_status: "CANCELLED" }], total: 1, page: 1, page_size: 20 });
  mount(<FeedbackAdministration participantId="p1" />);
  const option = await screen.findByRole("option", { name: /Tài khoản bị khóa/ });
  expect((option as HTMLOptionElement).disabled).toBe(true);
  await screen.findByText(/đã có phân công bị hủy/);
});
it("keeps HR deadline input and requires confirmation before optional cancellation", async () => {
  mocks.role = "HR"; const user = userEvent.setup();
  const row = { ...assignment, relationship: "PEER", required: false, reviewer_name: "Bình", reviewer_id: "peer", reviewer_employee_id: "e2", reviewer_active: true };
  mocks.api.administration.mockResolvedValue({ items: [row], total: 1, page: 1, page_size: 20 });
  mocks.api.cancel.mockRejectedValue(new ApiClientError(409, "stale_evidence_version", "stale"));
  mount(<FeedbackAdministration participantId="p1" />);
  await user.click(await screen.findByRole("button", { name: "Mở phân công Bình" }));
  const editor = screen.getByRole("region", { name: "Chi tiết phân công" });
  fireEvent.change(within(editor).getByLabelText("Hạn gửi mới (múi giờ thiết bị)"), { target: { value: "2027-01-01T10:00" } });
  await user.click(within(editor).getByRole("button", { name: "Hủy phân công tùy chọn" }));
  expect(mocks.api.cancel).not.toHaveBeenCalled();
  await user.click(within(editor).getByRole("button", { name: "Xác nhận thao tác" }));
  await within(editor).findByRole("alert");
  expect((within(editor).getByLabelText("Hạn gửi mới (múi giờ thiết bị)") as HTMLInputElement).value).toBe("2027-01-01T10:00");
  expect(mocks.api.cancel).toHaveBeenCalledWith("a1", { expected_assignment_version: 1, expected_evidence_version: 3, reason_code: "WRONG_SELECTION" });
});
it("HR viewing someone else's detail cannot see a submission form", async () => {
  mocks.role = "HR"; mocks.api.detail.mockResolvedValue({ ...assignment, reviewer_id: "other" });
  mount(<FeedbackDetail id="a1" />);
  await screen.findByRole("link", { name: "Mở quản trị phân công" });
  expect(screen.queryByLabelText("Nhận xét")).toBeNull();
});
it("paginates reviewer options and clears a selection before changing pages", async () => {
  mocks.role = "HR"; const user = userEvent.setup();
  mocks.api.options.mockImplementation((_p, _r, { page }) => Promise.resolve({ items: [{ reviewer_id: page === 1 ? "first" : "second", employee_id: "e1", employee_code: "NV01", display_name: page === 1 ? "Một" : "Hai", is_active: true, existing_assignment_id: null, existing_status: null }], total: 21, page, page_size: 20 }));
  mount(<FeedbackAdministration participantId="p1" />);
  await screen.findByRole("option", { name: "NV01 · Một" });
  await user.selectOptions(screen.getByLabelText("Người đánh giá hợp lệ"), "first");
  await user.click(screen.getAllByRole("button", { name: "Trang sau" })[0]!);
  await screen.findByRole("option", { name: "NV01 · Hai" });
  expect((screen.getByLabelText("Người đánh giá hợp lệ") as HTMLSelectElement).value).toBe("");
  expect(mocks.api.options).toHaveBeenLastCalledWith("p1", "SELF", { page: 2, q: "" });
});
it("explicitly reopens a cancelled row with both captured versions", async () => {
  mocks.role = "HR"; const user = userEvent.setup();
  const row = { ...assignment, relationship: "PEER", required: false, status: "CANCELLED", version: 2, evidence_version: 5, reviewer_name: "Bình", reviewer_id: "peer", reviewer_employee_id: "e2", reviewer_active: true };
  mocks.api.administration.mockResolvedValue({ items: [row], total: 1, page: 1, page_size: 20 });
  mocks.api.update.mockResolvedValue({ ...row, status: "OPEN", version: 3, evidence_version: 6 });
  mount(<FeedbackAdministration />);
  await user.click(await screen.findByRole("button", { name: "Mở phân công Bình" }));
  await user.click(screen.getByRole("button", { name: "Khôi phục phân công" }));
  expect(mocks.api.update).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Xác nhận thao tác" }));
  await waitFor(() => expect(mocks.api.update).toHaveBeenCalledWith("a1", { expected_assignment_version: 2, expected_evidence_version: 5, status: "OPEN", required: false, due_at: null }));
});
it("HR replaces a peer only after confirmation and keeps required under server control", async () => {
  mocks.role = "HR"; const user = userEvent.setup();
  const row = { ...assignment, relationship: "PEER", reviewer_name: "Bình", reviewer_id: "peer", reviewer_employee_id: "e2", reviewer_active: true };
  mocks.api.administration.mockResolvedValue({ items: [row], total: 1, page: 1, page_size: 20 });
  mocks.api.replace.mockResolvedValue({ ...row, id: "replacement", reviewer_id: "user", evidence_version: 4 });
  mount(<FeedbackAdministration />);
  await user.click(await screen.findByRole("button", { name: "Mở phân công Bình" }));
  await user.click(screen.getByRole("button", { name: "Thay người đánh giá" }));
  await user.selectOptions(await screen.findByLabelText("Người đánh giá hợp lệ"), "user");
  expect(mocks.api.replace).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Xác nhận thao tác" }));
  await waitFor(() => expect(mocks.api.replace).toHaveBeenCalledWith("a1", { expected_assignment_version: 1, expected_evidence_version: 3, reviewer_id: "user", due_at: null, reason_code: "WRONG_SELECTION" }));
});
it("defaults a peer assignment to optional while self and manager stay required", async () => {
  mocks.role = "HR"; const user = userEvent.setup(); mount(<FeedbackAdministration participantId="p1" />);
  await user.selectOptions(await screen.findByLabelText("Quan hệ người đánh giá"), "PEER");
  await screen.findByRole("option", { name: "NV01 · An" });
  expect((screen.getByLabelText("Bắt buộc hoàn thành") as HTMLInputElement).checked).toBe(false);
  await user.selectOptions(screen.getByLabelText("Người đánh giá hợp lệ"), "user");
  await user.click(screen.getByRole("button", { name: "Giao phản hồi" }));
  await waitFor(() => expect(mocks.api.create).toHaveBeenCalledWith(expect.objectContaining({ relationship: "PEER", required: false })));
});
it("shows overdue assignments in the inbox without offering an automatic retry", async () => {
  mocks.api.list.mockResolvedValue({ items: [{ ...assignment, due_at: "2020-01-01T00:00:00Z" }], total: 1, page: 1, page_size: 20 });
  mount(<FeedbackInbox />);
  await screen.findByText("Đã quá hạn — liên hệ HR gia hạn");
  expect(mocks.api.submit).not.toHaveBeenCalled();
});
it("changing required does not rewrite an untouched deadline or truncate its precision", async () => {
  mocks.role = "HR"; const user = userEvent.setup();
  const row = { ...assignment, relationship: "PEER", due_at: "2099-01-01T10:00:45.123456Z", reviewer_name: "Bình", reviewer_id: "peer", reviewer_employee_id: "e2", reviewer_active: true };
  mocks.api.administration.mockResolvedValue({ items: [row], total: 1, page: 1, page_size: 20 });
  mocks.api.update.mockResolvedValue({ ...row, required: false });
  mount(<FeedbackAdministration />);
  await user.click(await screen.findByRole("button", { name: "Mở phân công Bình" }));
  await user.click(screen.getByLabelText("Phản hồi bắt buộc"));
  await user.click(screen.getByRole("button", { name: "Lưu phân công" }));
  await user.click(screen.getByRole("button", { name: "Xác nhận thao tác" }));
  await waitFor(() => expect(mocks.api.update).toHaveBeenCalledWith("a1", { expected_assignment_version: 1, expected_evidence_version: 3, required: false }));
});
