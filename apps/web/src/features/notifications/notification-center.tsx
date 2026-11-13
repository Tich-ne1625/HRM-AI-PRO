"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useContext, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api-client";
import { useAuth } from "../auth/auth-provider";
import { DetailContext, detailLocation } from "../workspace/detail-context";
import { WorkspaceDialog } from "../workspace/dialog";
import { notificationApi } from "./api";

export function NotificationCenter() {
  const { user } = useAuth();
  const cache = useQueryClient();
  const router = useRouter();
  const details = useContext(DetailContext);
  const [opened, setOpened] = useState(false);
  const [tab, setTab] = useState<"inbox" | "tasks">("inbox");
  const [page, setPage] = useState(1);
  const [unread, setUnread] = useState(false);
  const [live, setLive] = useState(false);
  const key = ["notifications", user?.id, user?.role];
  const notices = useQuery({ queryKey: [...key, "inbox", page, unread], queryFn: () => notificationApi.list(page, unread), enabled: !!user, refetchInterval: live ? false : 15000 });
  const tasks = useQuery({ queryKey: [...key, "tasks"], queryFn: notificationApi.tasks, enabled: !!user && opened && tab === "tasks", refetchInterval: live ? false : 15000 });
  const refresh = () => cache.invalidateQueries({ queryKey: ["notifications"] });
  const read = useMutation({ mutationFn: notificationApi.read, onSuccess: refresh });
  const readAll = useMutation({ mutationFn: notificationApi.readAll, onSuccess: refresh });
  const userId = user?.id;
  const userRole = user?.role;

  useEffect(() => {
    if (!userId || !userRole || typeof EventSource === "undefined") return;
    let disposed = false;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let delay = 2000;
    const recover = () => {
      source?.close(); setLive(false);
      if (disposed || timer) return;
      timer = setTimeout(() => {
        timer = undefined;
        void apiFetch("/api/v1/auth/me").then(() => cache.invalidateQueries({ queryKey: ["auth", "me"] })).then(() => { if (!disposed) connect(); }).catch(() => { if (!disposed) recover(); });
      }, delay);
      delay = Math.min(delay * 2, 30000);
    };
    const changed = () => {
      if (disposed) return;
      for (const domain of ["notifications", "dashboard", "organization", "reviews", "feedback", "performance", "ai"]) void cache.invalidateQueries({ queryKey: [domain] });
    };
    const connect = () => {
      source = new EventSource("/api/v1/notifications/events", { withCredentials: true });
      source.onopen = () => { if (!disposed) { delay = 2000; setLive(true); } };
      source.addEventListener("change", changed);
      source.addEventListener("session", recover);
      source.addEventListener("reconnect", recover);
      source.onerror = recover;
    };
    connect();
    return () => { disposed = true; source?.close(); if (timer) clearTimeout(timer); };
  }, [userId, userRole, cache]);

  const openWork = (href: string) => {
    setOpened(false);
    const location = detailLocation(href);
    if (location && details) details.open(location);
    else router.push(href);
  };
  const count = notices.data?.unread_count ?? 0;
  return <>
    <button type="button" className="notification-trigger" aria-label={`Thông báo${count ? `, ${count} chưa đọc` : ""}`} onClick={() => setOpened(true)}>
      <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4" /></svg>
      <span>Thông báo</span>{count > 0 && <span className="notification-count">{count > 99 ? "99+" : count}</span>}
    </button>
    {opened && <WorkspaceDialog title="Thông báo và công việc" close={() => setOpened(false)} variant="sidebar">
      <p className="notification-connection" role="status">{live ? "Đang cập nhật trực tiếp" : "Đang kết nối lại · tự kiểm tra định kỳ"}</p>
      <div className="notification-tabs" role="group" aria-label="Nội dung thông báo"><button type="button" aria-pressed={tab === "inbox"} onClick={() => setTab("inbox")}>Thông báo{count ? ` (${count})` : ""}</button><button type="button" aria-pressed={tab === "tasks"} onClick={() => setTab("tasks")}>Việc cần làm</button></div>
      {tab === "inbox" ? <>
        <div className="notification-tools"><label><input type="checkbox" checked={unread} onChange={(event) => { setUnread(event.target.checked); setPage(1); }} />Chỉ chưa đọc</label><button type="button" disabled={!count || readAll.isPending} onClick={() => readAll.mutate()}>Đọc tất cả</button></div>
        {notices.isPending && <p role="status">Đang tải thông báo…</p>}
        {notices.isError && <p role="alert">Không tải được thông báo. <button onClick={() => { void notices.refetch(); }}>Thử lại</button></p>}
        {!notices.isError && notices.data && <>
          {!notices.data.items.length && <div className="notification-empty"><h3>{unread ? "Bạn đã đọc hết thông báo" : "Chưa có thông báo mới"}</h3><p>Chọn Việc cần làm để xem các hồ sơ và phiếu đang chờ.</p></div>}
          <ul className="notification-list">{notices.data.items.map((item) => <li key={item.id} className={item.read_at ? "is-read" : "is-unread"}>
            <button type="button" className="notification-item" disabled={read.isPending} onClick={() => { void read.mutateAsync(item.id).then(() => openWork(item.href)).catch(() => {}); }}><span className="notification-item-title">{!item.read_at && <span className="unread-dot" aria-label="Chưa đọc" />}{item.title}</span><span>{item.message}</span><small>{new Date(item.created_at).toLocaleString("vi-VN")} · {item.read_at ? "Đã đọc" : "Chưa đọc"}</small></button>
            {!item.read_at && <button type="button" className="notification-read" disabled={read.isPending} onClick={() => read.mutate(item.id)}>Đánh dấu đã đọc</button>}
          </li>)}</ul>
          {notices.data.total > 20 && <div className="pagination"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>Trang trước</button><span>Trang {page}</span><button disabled={page * 20 >= notices.data.total} onClick={() => setPage(page + 1)}>Trang sau</button></div>}
        </>}
        {(read.isError || readAll.isError) && <p role="alert">Chưa lưu được trạng thái đã đọc. Hãy thử lại.</p>}
      </> : <>
        <p className="help-text">Đọc thông báo không hoàn thành công việc. Danh sách này đối chiếu dữ liệu hiện tại.</p>
        {tasks.isPending && <p role="status">Đang kiểm tra công việc…</p>}
        {tasks.isError && <p role="alert">Không tải được công việc. <button onClick={() => { void tasks.refetch(); }}>Thử lại</button></p>}
        {!tasks.isError && tasks.data && <><ul className="notification-list">{tasks.data.items.map((item) => <li key={item.id}><button type="button" className="notification-item" onClick={() => openWork(item.href)}><small>{item.waiting ? "ĐANG CHỜ PHỐI HỢP" : "VIỆC CỦA BẠN"}</small><strong>{item.title}</strong><span>{item.detail}</span></button></li>)}</ul>{!tasks.data.items.length && <div className="notification-empty"><h3>Không còn việc đang chờ trong phạm vi của bạn</h3></div>}{tasks.data.truncated && <p>Hiển thị tối đa 20 phiếu và 20 hồ sơ ưu tiên. Mở chu kỳ để xem đầy đủ.</p>}</>}
      </>}
    </WorkspaceDialog>}
  </>;
}
