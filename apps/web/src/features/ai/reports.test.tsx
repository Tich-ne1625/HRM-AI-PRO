// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { SavedAIReports } from "./reports";

const mocks = vi.hoisted(() => ({ role: "HR", cycles: vi.fn(), reports: vi.fn(), detail: vi.fn(), generate: vi.fn() }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { id: "u1", role: mocks.role } }) }));
vi.mock("../cycles/api", () => ({ reviewApi: { cycles: mocks.cycles } }));
vi.mock("./api", () => ({ aiApi: { reports: mocks.reports, detail: mocks.detail, generate: mocks.generate } }));
const row = { id: "a1", review_id: "r1", employee_id: "e1", display_name: "An", cycle_id: "c1", cycle_name: "Quý IV", audience: "PUBLIC", generation_version: 1, calculation_version: 2, model: "test-model", generated_at: "2026-10-24T00:00:00Z", matches_current_calculation: true };
const analysis = { ...row, output: { summary: "Tư vấn đã lưu", strengths: [], improvement_areas: [], feedback_themes: [], recommended_actions: ["Thảo luận mục tiêu"], caveats: [] } };
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><SavedAIReports /></QueryClientProvider>);
  return view;
}
beforeEach(() => {
  vi.resetAllMocks(); mocks.role = "HR";
  mocks.cycles.mockResolvedValue({ items: [{ id: "c1", name: "Quý IV" }], total: 1 });
  mocks.reports.mockResolvedValue({ items: [row], total: 21, page: 1, page_size: 20 });
  mocks.detail.mockResolvedValue(analysis);
});
it("reads metadata first and opens saved content only after explicit selection", async () => {
  const user = userEvent.setup(); mount();
  await screen.findByText("Khớp lần tính hiện tại");
  expect(mocks.detail).not.toHaveBeenCalled();
  expect(screen.getByRole("link", { name: "Mở báo cáo" }).getAttribute("href")).toBe("/employees/e1/performance?cycle_id=c1");
  await user.click(screen.getByRole("button", { name: "Xem tư vấn 1 · An" }));
  await screen.findByText("Tư vấn đã lưu");
  expect(mocks.detail).toHaveBeenCalledWith("r1", "a1");
  await user.click(screen.getByRole("button", { name: "Đóng nội dung tư vấn" }));
  expect(screen.queryByText("Tư vấn đã lưu")).toBeNull();
  expect(mocks.generate).not.toHaveBeenCalled();
});
it("resets pagination and private content when filters change", async () => {
  const user = userEvent.setup(); mount(); await screen.findByText("Khớp lần tính hiện tại");
  await user.click(screen.getByRole("button", { name: "Trang sau" }));
  await waitFor(() => expect(mocks.reports).toHaveBeenCalledWith("PUBLIC", "", 2));
  await user.selectOptions(screen.getByLabelText("Phạm vi tư vấn"), "HR_PRIVATE");
  await waitFor(() => expect(mocks.reports).toHaveBeenCalledWith("HR_PRIVATE", "", 1));
  await user.selectOptions(screen.getByLabelText("Chu kỳ đánh giá"), "c1");
  await waitFor(() => expect(mocks.reports).toHaveBeenCalledWith("HR_PRIVATE", "c1", 1));
  expect(mocks.generate).not.toHaveBeenCalled();
});
it.each(["EMPLOYEE", "MANAGER"])("keeps %s reads PUBLIC with no private selector", async (role) => {
  mocks.role = role; mount(); await screen.findByText("Khớp lần tính hiện tại");
  expect(screen.queryByLabelText("Phạm vi tư vấn")).toBeNull();
  expect(mocks.reports.mock.calls.every((call) => call[0] === "PUBLIC")).toBe(true);
});
it("blocks ADMIN before fetching any personnel data", () => {
  mocks.role = "ADMIN"; mount(); expect(screen.getByRole("alert")).toBeTruthy();
  expect(mocks.reports).not.toHaveBeenCalled(); expect(mocks.cycles).not.toHaveBeenCalled();
});
it("distinguishes historical advice and an empty result", async () => {
  mocks.reports.mockResolvedValueOnce({ items: [{ ...row, matches_current_calculation: false }], total: 1 });
  const user = userEvent.setup(); mount(); await screen.findByText("Bản lịch sử");
  mocks.reports.mockResolvedValue({ items: [], total: 0 });
  await user.click(screen.getByRole("button", { name: "Tải lại danh sách" }));
  await screen.findByRole("heading", { name: "Chưa có tư vấn đã lưu" });
  expect(screen.getByRole("button", { name: "Trang sau" })).toHaveProperty("disabled", true);
});
it("offers retry for failed list and content loads without displaying cached unauthorized detail", async () => {
  mocks.reports.mockRejectedValueOnce(new Error("network"));
  const user = userEvent.setup(); mount(); await screen.findByRole("alert");
  await user.click(screen.getByRole("button", { name: "Tải lại danh sách" }));
  await screen.findByText("Khớp lần tính hiện tại"); mocks.detail.mockRejectedValueOnce(new Error("forbidden"));
  await user.click(screen.getByRole("button", { name: "Xem tư vấn 1 · An" }));
  await screen.findByText("Không tải được tư vấn hoặc quyền truy cập đã thay đổi.");
  expect(screen.queryByText("Tư vấn đã lưu")).toBeNull();
  await user.click(screen.getByRole("button", { name: "Thử tải lại nội dung" }));
  await screen.findByText("Tư vấn đã lưu"); expect(mocks.generate).not.toHaveBeenCalled();
});
