// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import type { Report } from "../performance/api";
import { AISection } from "./section";

const mocks = vi.hoisted(() => ({ role: "HR", api: { state: vi.fn(), generate: vi.fn(), history: vi.fn(), detail: vi.fn() } }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { id: "u1", role: mocks.role } }) }));
vi.mock("./api", () => ({ aiApi: mocks.api }));
const report = { review_id: "r1", evidence_version: 8, state: "CURRENT", current_result: { calculation_version: 1 } } as Report;
const state = { configured: true, state: "NOT_GENERATED", can_generate: true, can_retry: false, current_analysis: null, last_successful_analysis: null, latest_attempt: null };
function mount() {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={cache}><AISection report={report} /></QueryClientProvider>); return cache;
}
beforeEach(() => { vi.resetAllMocks(); sessionStorage.clear(); mocks.role = "HR"; mocks.api.state.mockResolvedValue(state); });
it("never generates on page view or query invalidation", async () => {
  const cache = mount(); await screen.findByRole("button", { name: "Tạo tư vấn AI" });
  await act(async () => { await cache.invalidateQueries({ queryKey: ["ai"] }); });
  expect(mocks.api.generate).not.toHaveBeenCalled();
});
it("does not fetch for ADMIN", () => { mocks.role = "ADMIN"; mount(); expect(mocks.api.state).not.toHaveBeenCalled(); });
it("does not fetch private data until HR selects the internal scope", async () => {
  const user = userEvent.setup(); mount(); await screen.findByRole("button", { name: "Nội bộ HR" });
  expect(mocks.api.state.mock.calls.every((call) => call[1] === "PUBLIC")).toBe(true);
  await user.click(screen.getByRole("button", { name: "Nội bộ HR" }));
  await waitFor(() => expect(mocks.api.state).toHaveBeenCalledWith("r1", "HR_PRIVATE"));
});
it("employees read public advice without generation/private controls", async () => {
  mocks.role = "EMPLOYEE"; mount(); await screen.findByRole("heading", { name: "Tư vấn AI" });
  expect(screen.queryByRole("button", { name: "Nội bộ HR" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Tạo tư vấn AI" })).toBeNull();
  expect(mocks.api.state.mock.calls.every((call) => call[1] === "PUBLIC")).toBe(true);
});
it("requires explicit checked confirmation and captured versions", async () => {
  mocks.api.generate.mockResolvedValue({ id: "a1", status: "SUCCEEDED" });
  const user = userEvent.setup(); mount();
  await user.click(await screen.findByRole("button", { name: "Tạo tư vấn AI" }));
  const confirm = screen.getByRole("button", { name: "Xác nhận tạo tư vấn" });
  expect(confirm).toHaveProperty("disabled", true);
  await user.click(screen.getByRole("checkbox")); await user.click(confirm);
  await waitFor(() => expect(mocks.api.generate).toHaveBeenCalledWith("r1", expect.objectContaining({ expected_calculation_version: 1, expected_evidence_version: 8, audience: "PUBLIC", regenerate: false, client_request_id: expect.any(String) })));
});
it("keyless deployment explains configuration without blocking scores", async () => {
  mocks.api.state.mockResolvedValue({ ...state, configured: false, can_generate: false });
  mount(); await screen.findByText(/Gemini chưa được cấu hình/);
  expect(screen.queryByRole("button", { name: "Tạo tư vấn AI" })).toBeNull();
});

it("replays a lost response with the same intent only after another click", async () => {
  mocks.api.generate.mockRejectedValueOnce(new Error("network"));
  mocks.api.generate.mockResolvedValueOnce({ id: "a1", status: "SUCCEEDED" });
  const user = userEvent.setup(); const cache = mount();
  await user.click(await screen.findByRole("button", { name: "Tạo tư vấn AI" }));
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Xác nhận tạo tư vấn" }));
  await screen.findByRole("alert");
  const original = mocks.api.generate.mock.calls[0]![1];
  await act(async () => { await cache.invalidateQueries({ queryKey: ["ai"] }); });
  expect(mocks.api.generate).toHaveBeenCalledTimes(1);
  expect(JSON.parse(sessionStorage.getItem("insighthr-ai-intent:u1:r1:PUBLIC")!)).toEqual(original);
  await user.click(screen.getByRole("button", { name: "Kiểm tra yêu cầu vừa gửi" }));
  await waitFor(() => expect(mocks.api.generate).toHaveBeenCalledTimes(2));
  expect(mocks.api.generate.mock.calls[1]![1]).toEqual(original);
  await waitFor(() => expect(sessionStorage.getItem("insighthr-ai-intent:u1:r1:PUBLIC")).toBeNull());
});

it("restores a pending intent after reload without automatically posting", async () => {
  sessionStorage.setItem("insighthr-ai-intent:u1:r1:PUBLIC", JSON.stringify({
    client_request_id: "11111111-1111-4111-8111-111111111111", audience: "PUBLIC",
    expected_calculation_version: 1, expected_evidence_version: 8, regenerate: false,
  }));
  mount(); await screen.findByRole("button", { name: "Kiểm tra yêu cầu vừa gửi" });
  expect(mocks.api.generate).not.toHaveBeenCalled();
});

it("blocks an unsent confirmation when the calculation changes", async () => {
  const user = userEvent.setup();
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = (value: Report) => <QueryClientProvider client={cache}><AISection report={value} /></QueryClientProvider>;
  const rendered = render(view(report));
  await user.click(await screen.findByRole("button", { name: "Tạo tư vấn AI" }));
  await user.click(screen.getByRole("checkbox"));
  rendered.rerender(view({ ...report, evidence_version: 9, current_result: { calculation_version: 2 } } as Report));
  expect((await screen.findByRole("alert")).textContent).toContain("Dữ liệu xác nhận đã thay đổi");
  expect(screen.getByRole("button", { name: "Xác nhận tạo tư vấn" })).toHaveProperty("disabled", true);
  expect(mocks.api.generate).not.toHaveBeenCalled();
});

it("renders provider text as text and removes private content after a role change", async () => {
  const row = { id: "private", generation_version: 1, calculation_version: 1, model: "test", output: {
    summary: "<img src=x onerror=alert(1)> PRIVATE", strengths: [], improvement_areas: [],
    feedback_themes: [], recommended_actions: [], caveats: ["Advisory"],
  } };
  mocks.api.state.mockImplementation((_review, audience) => Promise.resolve(
    audience === "HR_PRIVATE" ? { ...state, current_analysis: row } : state));
  const user = userEvent.setup();
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = () => <QueryClientProvider client={cache}><AISection report={report} /></QueryClientProvider>;
  const rendered = render(view());
  await user.click(await screen.findByRole("button", { name: "Nội bộ HR" }));
  await screen.findByText(row.output.summary);
  expect(rendered.container.querySelector("img")).toBeNull();
  mocks.role = "EMPLOYEE"; rendered.rerender(view());
  await waitFor(() => expect(screen.queryByText(row.output.summary)).toBeNull());
  expect(screen.queryByRole("button", { name: "Nội bộ HR" })).toBeNull();
});

it("drops the open confirmation when switching to another review", async () => {
  const user = userEvent.setup();
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = (value: Report) => <QueryClientProvider client={cache}><AISection report={value} /></QueryClientProvider>;
  const rendered = render(view(report));
  await user.click(await screen.findByRole("button", { name: "Tạo tư vấn AI" }));
  await user.click(screen.getByRole("checkbox"));
  rendered.rerender(view({ ...report, review_id: "another-review" }));
  await screen.findByRole("button", { name: "Tạo tư vấn AI" });
  expect(screen.queryByRole("button", { name: "Xác nhận tạo tư vấn" })).toBeNull();
  expect(mocks.api.generate).not.toHaveBeenCalled();
});
