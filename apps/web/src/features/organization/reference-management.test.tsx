// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ReferenceManagement } from "./reference-management";

const mocks = vi.hoisted(() => ({ role: "HR", references: vi.fn(), saveReference: vi.fn() }));
vi.mock("../auth/auth-provider", () => ({ useAuth: () => ({ user: { role: mocks.role } }) }));
vi.mock("./api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./api")>(), organizationApi: mocks,
}));

function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ReferenceManagement kind="departments" />
  </QueryClientProvider>);
}
beforeEach(() => {
  vi.clearAllMocks(); mocks.role = "HR";
  mocks.references.mockResolvedValue({ items: [{ id: "eng", code: "ENG", name: "Engineering", is_active: true }], total: 1, page: 1, page_size: 20 });
  mocks.saveReference.mockResolvedValue({});
});

it("lets HR create reference data through labeled controls", async () => {
  const user = userEvent.setup(); mount();
  expect(await screen.findByText("Engineering")).toBeTruthy();
  await user.click(screen.getByText("Thêm mới phòng ban"));
  await user.type(screen.getByLabelText("Mã phòng ban"), "qa");
  await user.type(screen.getByLabelText("Tên phòng ban"), "Quality");
  await user.click(screen.getByRole("button", { name: "Thêm phòng ban" }));
  await waitFor(() => expect(mocks.saveReference).toHaveBeenCalledWith("departments", null, {
    code: "QA", name: "Quality", is_active: true,
  }));
});

it("requires confirmation to retire reference data", async () => {
  const user = userEvent.setup(); mount();
  await screen.findByText("Engineering");
  await user.click(screen.getByRole("button", { name: "Ngừng hoạt động ENG" }));
  expect(mocks.saveReference).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Xác nhận ngừng hoạt động" }));
  await waitFor(() => expect(mocks.saveReference).toHaveBeenCalledWith("departments", "eng", { is_active: false }));
});

it("shows scoped read-only references to managers", async () => {
  mocks.role = "MANAGER"; mount();
  await screen.findByText("Engineering");
  expect(screen.queryByRole("button", { name: "Thêm phòng ban" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Ngừng hoạt động ENG" })).toBeNull();
});

it("does not issue reference requests for ADMIN", () => {
  mocks.role = "ADMIN"; mount();
  expect(mocks.references).not.toHaveBeenCalled();
  expect(screen.getByRole("alert").textContent).toContain("không có quyền");
});

it("keeps entered data when a save fails", async () => {
  mocks.saveReference.mockRejectedValue(new Error("offline"));
  const user = userEvent.setup(); mount();
  await screen.findByText("Engineering");
  await user.click(screen.getByText("Thêm mới phòng ban"));
  await user.type(screen.getByLabelText("Mã phòng ban"), "QA");
  await user.type(screen.getByLabelText("Tên phòng ban"), "Quality");
  await user.click(screen.getByRole("button", { name: "Thêm phòng ban" }));
  await screen.findByRole("alert");
  expect((screen.getByLabelText("Tên phòng ban") as HTMLInputElement).value).toBe("Quality");
});
