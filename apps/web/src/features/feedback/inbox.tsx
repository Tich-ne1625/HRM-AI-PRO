"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { Pagination } from "../organization/shared";
import { feedbackApi, type Status } from "./api";
import { deadline, FeedbackError, relationships, statuses, useDisplayClock } from "./shared";

export function FeedbackInbox() {
  const { user } = useAuth();
  const now = useDisplayClock();
  const [page, setPage] = useState(1), [status, setStatus] = useState<Status | "">("");
  const query = useQuery({ queryKey: ["feedback", "mine", user?.id, page, status],
    queryFn: () => feedbackApi.list({ view: "mine", page, status }), enabled: !!user });
  return <section className="auth-card wide"><div className="section-heading"><div><p className="eyebrow">PHẢN HỒI 360</p><h1>Phản hồi của tôi</h1></div>
    {user?.role === "HR" && <Link className="action-link" href="/feedback-administration">Quản trị phân công</Link>}</div>
    <p>Các phân công được giao đích danh cho bạn. Mỗi phản hồi chỉ gửi một lần; HR có quyền xem nội dung để quản trị đánh giá.</p>
    <div className="directory-reference-filter"><label htmlFor="inbox-status">Trạng thái phản hồi</label><select id="inbox-status" value={status} onChange={(e) => { setStatus(e.target.value as Status | ""); setPage(1); }}><option value="">Tất cả trạng thái</option>{Object.entries(statuses).map(([v, label]) => <option value={v} key={v}>{label}</option>)}</select></div>
    {query.isPending && <p role="status">Đang tải phân công…</p>}
    {query.isError && <FeedbackError error={query.error} reload={() => { void query.refetch(); }} />}
    {!query.isError && query.data && <><div className="feedback-cards">{query.data.items.map((row) => <article className="inbox-card" key={row.id}><div className="section-heading"><span className={`badge ${row.status === "SUBMITTED" ? "active" : ""}`}>{statuses[row.status]}</span><span className="help-text">{relationships[row.relationship]}{row.required ? " · Bắt buộc" : " · Tùy chọn"}</span></div>
      <h2><Link href={`/feedback/${row.id}`}>{row.employee_code} · {row.display_name}</Link></h2><p>{row.cycle_name} · {row.start_date} – {row.end_date}</p><p className="help-text">Hạn: {deadline(row.due_at)}</p>{row.status === "OPEN" && row.due_at && now >= Date.parse(row.due_at) && <p className="field-warning">Đã quá hạn — liên hệ HR gia hạn</p>}</article>)}</div>
      {!query.data.items.length && <div className="empty-state"><h2>Chưa có phân công phù hợp</h2><p>Thay bộ lọc hoặc quay lại khi HR đã giao phản hồi.</p></div>}
      <Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} /></>}
  </section>;
}
