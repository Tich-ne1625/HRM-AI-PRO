"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { reviewApi } from "../cycles/api";
import { Pagination } from "../organization/shared";
import { aiApi, type Audience, type SavedReport } from "./api";
import { AnalysisContent } from "./section";

export function SavedAIReports() {
  const { user } = useAuth();
  if (!user || !["HR", "MANAGER", "EMPLOYEE"].includes(user.role)) {
    return <section className="auth-card"><h1>Tư vấn AI đã lưu</h1><p role="alert">Bạn không có quyền xem tư vấn AI của nhân sự.</p><Link href="/dashboard">Về tổng quan</Link></section>;
  }
  return <Directory key={`${user.id}-${user.role}`} userId={user.id} hr={user.role === "HR"} />;
}

function Directory({ userId, hr }: { userId: string; hr: boolean }) {
  const [filters, setFilters] = useState<{ audience: Audience; cycle: string; page: number }>({ audience: "PUBLIC", cycle: "", page: 1 });
  const [selected, setSelected] = useState<SavedReport | null>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const cycles = useQuery({ queryKey: ["reviews", "ai-cycle-options", userId, hr], queryFn: () => reviewApi.cycles({ page_size: 100 }) });
  const query = useQuery({ queryKey: ["ai", "reports", userId, hr, filters], queryFn: () => aiApi.reports(filters.audience, filters.cycle, filters.page) });
  const change = (patch: Partial<typeof filters>) => { setSelected(null); setFilters((old) => ({ ...old, ...patch })); };
  return <section className="auth-card wide" aria-labelledby="ai-reports-title">
    <div className="section-heading"><div><p className="eyebrow">KẾT QUẢ ĐÃ LƯU</p><h1 id="ai-reports-title">Tư vấn AI</h1></div><button type="button" className="secondary" disabled={query.isFetching || cycles.isFetching} onClick={() => { void query.refetch(); void cycles.refetch(); }}>Tải lại danh sách</button></div>
    <p>Xem các bản tư vấn đã tạo thành công trong phạm vi được phép. Mỗi dòng là một lần tư vấn; mở hoặc tải lại trang không gọi Gemini.</p>
    <div className="form-grid ai-report-filters">
      <div><label htmlFor="ai-report-cycle">Chu kỳ đánh giá</label><select id="ai-report-cycle" value={filters.cycle} onChange={(event) => change({ cycle: event.target.value, page: 1 })} disabled={cycles.isPending}>
        <option value="">Tất cả chu kỳ được phép</option>{cycles.data?.items.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
      </select>{cycles.isError && <p role="alert">Không tải được bộ lọc chu kỳ. Bạn vẫn xem được danh sách; bấm tải lại để thử lại.</p>}{cycles.data && cycles.data.total > cycles.data.items.length && <p className="help-text">Bộ lọc hiển thị 100 chu kỳ gần nhất. Chọn tất cả để xem các bản cũ hơn.</p>}</div>
      {hr && <div><label htmlFor="ai-report-audience">Phạm vi tư vấn</label><select id="ai-report-audience" value={filters.audience} onChange={(event) => change({ audience: event.target.value as Audience, page: 1 })}><option value="PUBLIC">Tư vấn chung</option><option value="HR_PRIVATE">Nội bộ HR</option></select></div>}
    </div>
    {filters.audience === "HR_PRIVATE" && <p className="state-notice">Nội dung nội bộ HR. Chỉ HR có quyền truy cập các bản phân tích này.</p>}
    {query.isPending && <p role="status">Đang tải tư vấn đã lưu…</p>}
    {query.isError && <p role="alert">Không tải được danh sách trong phạm vi này. Hãy tải lại hoặc kiểm tra quyền và phiên đăng nhập.</p>}
    {!query.isError && query.data && <>
      {!query.data.items.length ? <div className="empty-state"><h2>Chưa có tư vấn đã lưu</h2><p>Thử đổi bộ lọc. HR có thể tạo tư vấn từ báo cáo có kết quả hợp lệ sau khi xác nhận gửi dữ liệu.</p><Link href="/review-cycles">Mở chu kỳ đánh giá →</Link></div> : <div className="table-scroll" tabIndex={0} role="region" aria-label="Danh sách tư vấn AI, có thể cuộn ngang"><table className="ai-reports-table"><caption>{query.data.total} lần tư vấn thành công · mới nhất trước</caption><thead><tr><th scope="col">Nhân viên / chu kỳ</th><th scope="col">Phiên bản</th><th scope="col">Đối chiếu điểm</th><th scope="col">Ngày tạo / model</th><th scope="col">Thao tác</th></tr></thead><tbody>{query.data.items.map((row) => <tr key={row.id}>
        <th scope="row">{row.display_name}<small>{row.cycle_name}</small></th><td>Tư vấn {row.generation_version}<small>Lần tính {row.calculation_version}</small></td>
        <td><span className={`badge ${row.matches_current_calculation ? "active" : ""}`}>{row.matches_current_calculation ? "Khớp lần tính hiện tại" : "Bản lịch sử"}</span></td>
        <td><time dateTime={row.generated_at}>{new Date(row.generated_at).toLocaleString("vi-VN")}</time><small>{row.model}</small></td>
        <td><div className="row-actions"><button type="button" className="secondary" onClick={(event) => { trigger.current = event.currentTarget; setSelected(row); }}>Xem tư vấn {row.generation_version} · {row.display_name}</button><Link href={`/employees/${row.employee_id}/performance?cycle_id=${encodeURIComponent(row.cycle_id)}`}>Mở báo cáo</Link></div></td>
      </tr>)}</tbody></table></div>}
      <Pagination page={filters.page} total={query.data.total} pending={query.isFetching} onPage={(page) => change({ page })} />
    </>}
    {selected && !query.isError && <SavedDetail key={`${selected.id}-${filters.audience}`} row={query.data?.items.find((row) => row.id === selected.id) ?? selected} userId={userId} close={() => { setSelected(null); trigger.current?.focus(); }} />}
  </section>;
}

function SavedDetail({ row, userId, close }: { row: SavedReport; userId: string; close: () => void }) {
  const heading = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); heading.current?.scrollIntoView?.({ block: "start" }); }, []);
  const query = useQuery({ queryKey: ["ai", "saved-detail", userId, row.audience, row.review_id, row.id], queryFn: () => aiApi.detail(row.review_id, row.id) });
  return <section className="ai-saved-detail" aria-labelledby="saved-ai-title"><div className="section-heading"><h2 ref={heading} tabIndex={-1} id="saved-ai-title">Tư vấn {row.generation_version} · {row.display_name}</h2><button type="button" className="secondary" onClick={close}>Đóng nội dung tư vấn</button></div>
    <p>{row.cycle_name} · {row.audience === "PUBLIC" ? "Tư vấn chung" : "Nội bộ HR"} · Nội dung tham khảo, không thay đổi điểm số.</p>
    {!row.matches_current_calculation && <p className="state-notice">Bản lịch sử không khớp kết quả hiện tại; chỉ dùng để đối chiếu.</p>}
    {query.isPending && <p role="status">Đang tải nội dung…</p>}{query.isError && <><p role="alert">Không tải được tư vấn hoặc quyền truy cập đã thay đổi.</p><button type="button" className="secondary" onClick={() => { void query.refetch(); }}>Thử tải lại nội dung</button></>}
    {!query.isError && query.data && <AnalysisContent row={query.data} />}
  </section>;
}
