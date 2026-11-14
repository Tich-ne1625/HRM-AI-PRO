"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

export function WorkspaceDialog({ title, close, children, focusKey, variant, eyebrow = "CHI TIẾT CÔNG VIỆC" }: { title: string; close: () => void; children: ReactNode; focusKey?: string; variant?: "sidebar" | "content"; eyebrow?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (dialog && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    return () => {
      dialog?.close?.();
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, []);
  useEffect(() => {
    if (focusKey === undefined) return;
    const dialog = ref.current;
    dialog?.querySelector<HTMLButtonElement>(".dialog-close")?.focus({ preventScroll: true });
    if (dialog) dialog.scrollTop = 0;
  }, [focusKey]);
  return <dialog ref={ref} className={`workspace-dialog${variant === "sidebar" ? " notification-sidebar" : variant === "content" ? " collaboration-dialog" : ""}`} aria-labelledby={titleId} onCancel={(event) => { event.preventDefault(); close(); }} onKeyDown={(event) => {
    if (event.key !== "Tab") return;
    const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('a[href], button:not(:disabled), input:not(:disabled):not([type="hidden"]), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'))
      .filter((element) => element.tabIndex >= 0 && element.getClientRects().length > 0);
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first && last) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last && first) { event.preventDefault(); first.focus(); }
  }}>
    <div className="workspace-dialog-header"><div><span className="eyebrow">{eyebrow}</span><h2 id={titleId}>{title}</h2></div>
      <button type="button" className="dialog-close" aria-label={`Đóng ${title}`} onClick={close}><span aria-hidden="true">×</span><span>Đóng</span></button></div>
    <div className="workspace-dialog-content">{children}</div>
  </dialog>;
}
