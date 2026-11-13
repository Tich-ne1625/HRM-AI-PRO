// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { DetailContext, detailLocation } from "./detail-context";
import DetailLink from "./detail-link";
import { WorkspaceDialog } from "./dialog";
import { useState } from "react";

it("opens evaluation tabs within one context without navigating the background", async () => {
  const open = vi.fn();
  const user = userEvent.setup();
  render(<DetailContext value={{ open, close: vi.fn(), active: true }}><DetailLink href="/employees/e1/kpis?cycle_id=c1">KPI</DetailLink></DetailContext>);
  await user.click(screen.getByRole("link", { name: "KPI" }));
  expect(open).toHaveBeenCalledWith(expect.objectContaining({ kind: "kpis", id: "e1", cycle: "c1" }));
});

it("closes the detail on its list link instead of leaving the current workspace", async () => {
  const close = vi.fn();
  const user = userEvent.setup();
  render(<DetailContext value={{ open: vi.fn(), close, active: true }}><DetailLink href="/review-cycles">Danh sách</DetailLink></DetailContext>);
  await user.click(screen.getByRole("link", { name: "Danh sách" }));
  expect(close).toHaveBeenCalledOnce();
});

it("preserves the background filter when a dialog is closed and restores focus", async () => {
  const user = userEvent.setup();
  function Harness() {
    const [open, setOpen] = useState(false);
    return <><label>Bộ lọc<input /></label><button onClick={() => setOpen(true)}>Mở</button>
      {open && <WorkspaceDialog title="Hồ sơ" close={() => setOpen(false)}><p>Chi tiết</p></WorkspaceDialog>}</>;
  }
  render(<Harness />);
  await user.type(screen.getByLabelText("Bộ lọc"), "Bình");
  const trigger = screen.getByRole("button", { name: "Mở" });
  await user.click(trigger);
  expect(screen.getByRole("dialog", { name: "Hồ sơ" })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Đóng Hồ sơ" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect((screen.getByLabelText("Bộ lọc") as HTMLInputElement).value).toBe("Bình");
  expect(document.activeElement).toBe(trigger);
  await user.click(trigger);
  fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true, cancelable: true }));
  expect(screen.queryByRole("dialog")).toBeNull();
});

it.each(["https://outside.example/employees/e1", "/employees/e1/kpis", "/admin/users"])("does not intercept unsupported or incomplete destination %s", (href) => {
  expect(detailLocation(href)).toBeNull();
});

it("returns keyboard focus to the dialog when a detail tab replaces its content", async () => {
  const user = userEvent.setup();
  const close = vi.fn();
  const view = render(<WorkspaceDialog title="Đánh giá" close={close} focusKey="kpis"><label>Thực tế<input /></label></WorkspaceDialog>);
  await user.click(screen.getByLabelText("Thực tế"));
  expect(document.activeElement).toBe(screen.getByLabelText("Thực tế"));
  view.rerender(<WorkspaceDialog title="Đánh giá" close={close} focusKey="feedback"><p>Tổng hợp phản hồi</p></WorkspaceDialog>);
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Đóng Đánh giá" }));
});

it("wraps Tab and Shift+Tab between visible dialog controls", () => {
  const rectangles = vi.spyOn(HTMLElement.prototype, "getClientRects").mockReturnValue([{}] as unknown as DOMRectList);
  try {
    render(<WorkspaceDialog title="Phiếu" close={vi.fn()}><button>Gửi</button></WorkspaceDialog>);
    const first = screen.getByRole("button", { name: "Đóng Phiếu" });
    const last = screen.getByRole("button", { name: "Gửi" });
    last.focus(); fireEvent.keyDown(last, { key: "Tab" }); expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true }); expect(document.activeElement).toBe(last);
  } finally { rectangles.mockRestore(); }
});
