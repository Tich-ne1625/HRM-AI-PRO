// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { DetailContext } from "../workspace/detail-context";
import { NotificationCenter } from "./notification-center";

const mocks = vi.hoisted(() => ({ list: vi.fn(), tasks: vi.fn(), read: vi.fn(), readAll: vi.fn(), open: vi.fn(), push: vi.fn(), fetch: vi.fn() }));
vi.mock("./api", () => ({ notificationApi: mocks }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { id: "u1", role: "HR" } }) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("../../lib/api-client", () => ({ apiFetch: mocks.fetch }));

class FakeSource {
  static instances: FakeSource[] = [];
  listeners = new Map<string, () => void>();
  onopen?: () => void;
  onerror?: () => void;
  close = vi.fn();
  constructor() { FakeSource.instances.push(this); }
  addEventListener(event: string, action: () => void) { this.listeners.set(event, action); }
}
const notice = { id: "n1", title: "Kết quả đã được tính", message: "An · Kỳ thử", href: "/employees/e1/performance?cycle_id=c1", created_at: "2026-11-14T01:00:00Z", read_at: null };
function mount() {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = render(<QueryClientProvider client={cache}><DetailContext.Provider value={{ open: mocks.open, close: vi.fn(), active: false }}><NotificationCenter /></DetailContext.Provider></QueryClientProvider>);
  return { ...view, cache };
}
beforeEach(() => {
  vi.resetAllMocks(); FakeSource.instances = [];
  vi.stubGlobal("EventSource", FakeSource);
  mocks.list.mockResolvedValue({ items: [notice], total: 1, unread_count: 1, page: 1, page_size: 20 });
  mocks.tasks.mockResolvedValue({ items: [{ id: "p1", title: "Kiểm tra và chốt", detail: "An · Kỳ thử", href: notice.href, waiting: false }], truncated: false });
  mocks.read.mockResolvedValue(undefined); mocks.readAll.mockResolvedValue(undefined);
});
afterEach(() => { vi.unstubAllGlobals(); });

it("refreshes durable inbox on server changes and disposes the live connection", async () => {
  const { unmount } = mount();
  await screen.findByRole("button", { name: "Thông báo, 1 chưa đọc" });
  const source = FakeSource.instances[0]!;
  const before = mocks.list.mock.calls.length;
  act(() => { source.onopen?.(); source.listeners.get("change")?.(); });
  await waitFor(() => expect(mocks.list.mock.calls.length).toBeGreaterThan(before));
  unmount(); expect(source.close).toHaveBeenCalledTimes(1);
});
it("marks a notice read before opening the same workspace detail", async () => {
  const user = userEvent.setup(); mount();
  await user.click(await screen.findByRole("button", { name: "Thông báo, 1 chưa đọc" }));
  await user.click(await screen.findByRole("button", { name: /Kết quả đã được tính/ }));
  await waitFor(() => expect(mocks.read).toHaveBeenCalledWith("n1", expect.anything()));
  await waitFor(() => expect(mocks.open).toHaveBeenCalledWith(expect.objectContaining({ kind: "performance", id: "e1", cycle: "c1" })));
  expect(screen.queryByRole("dialog")).toBeNull(); expect(mocks.push).not.toHaveBeenCalled();
});
it("keeps the sidebar and work when saving read state fails", async () => {
  mocks.read.mockRejectedValue(new Error("offline"));
  const user = userEvent.setup(); mount();
  await user.click(await screen.findByRole("button", { name: "Thông báo, 1 chưa đọc" }));
  await user.click(await screen.findByRole("button", { name: /Kết quả đã được tính/ }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("Chưa lưu"));
  expect(mocks.open).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Việc cần làm" }));
  await user.click(await screen.findByRole("button", { name: /Kiểm tra và chốt/ }));
  expect(mocks.open).toHaveBeenCalled(); expect(mocks.read).toHaveBeenCalledTimes(1);
});
it("reading all does not complete or submit pending work", async () => {
  const user = userEvent.setup(); mount();
  await user.click(await screen.findByRole("button", { name: "Thông báo, 1 chưa đọc" }));
  await user.click(screen.getByRole("button", { name: "Đọc tất cả" }));
  await waitFor(() => expect(mocks.readAll).toHaveBeenCalledTimes(1));
  await user.click(screen.getByRole("button", { name: "Việc cần làm" }));
  expect(await screen.findByRole("button", { name: /Kiểm tra và chốt/ })).toBeTruthy();
  expect(mocks.open).not.toHaveBeenCalled();
});
