"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { dashboardApi } from "./api";

function Metric({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>;
}

export function DashboardOverview() {
  const { user } = useAuth();
  const [cycle, setCycle] = useState("");
  const query = useQuery({ queryKey: ["dashboard", user?.id, user?.role, cycle],
    queryFn: () => dashboardApi.get(cycle), enabled: !!user, staleTime: 0 });
  const data = query.data;
  const admin = user?.role === "ADMIN";
  const scopes: Record<string, string> = { HR: "Toàn bộ nhân sự", MANAGER: "Bản thân và nhân viên trực tiếp", EMPLOYEE: "Kết quả của bản thân", ADMIN: "Quản trị tài khoản" };
  return <section className="auth-card dashboard" aria-labelledby="dashboard-title">
    <div className="section-heading"><div><p className="eyebrow">KHÔNG GIAN LÀM VIỆC</p><h1 id="dashboard-title">Tổng quan</h1><p>{scopes[user?.role ?? ""]}</p></div>
      <button type="button" className="secondary" disabled={query.isFetching} onClick={() => { void query.refetch(); }}>{query.isFetching ? "Đang tải…" : "Tải lại"}</button></div>
    {query.isPending && <p role="status">Đang tải tổng quan…</p>}
    {query.isError && <p role="alert">Không tải được tổng quan. Hãy thử tải lại hoặc kiểm tra phiên đăng nhập.</p>}
    {data && <>
      <div className="dashboard-task"><div><strong>Phản hồi của tôi</strong><p>{data.pending_feedback} nhiệm vụ còn mở trong các chu kỳ đang hoạt động.</p></div><Link href="/feedback">Mở hộp việc →</Link></div>
      {admin ? <>
        <div className="metric-grid"><Metric label="Tài khoản hoạt động" value={data.active_accounts ?? 0} /><Metric label="Tài khoản đã khóa" value={data.inactive_accounts ?? 0} /></div>
        <h2>Tài khoản theo vai trò</h2><div className="metric-grid">{Object.entries(data.account_roles ?? {}).map(([role, count]) => <Metric key={role} label={role} value={count} />)}</div>
        <div className="row-actions"><Link href="/admin/users">Quản lý tài khoản →</Link><Link href="/settings/scoring">Cấu hình chấm điểm →</Link></div>
      </> : <>
        <div className="dashboard-cycle"><label htmlFor="dashboard-cycle">Chu kỳ đánh giá</label><select id="dashboard-cycle" value={cycle || data.selected_cycle?.id || ""} onChange={(event) => setCycle(event.target.value)} disabled={!data.cycles?.length}>
          {!data.cycles?.length && <option value="">Chưa có chu kỳ trong phạm vi quyền</option>}
          {data.cycles?.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.status === "ACTIVE" ? "Đang hoạt động" : item.status === "CLOSED" ? "Đã đóng" : "Bản nháp"}</option>)}
        </select>{data.cycles_truncated && <small>Hiển thị 100 chu kỳ ưu tiên gần nhất và chu kỳ đang chọn.</small>}</div>
        <div className="metric-grid"><Metric label="Nhân viên đang làm việc" value={data.active_employees ?? 0} detail="Theo cơ cấu hiện tại và phạm vi quyền" />
          <Metric label="Người tham gia chu kỳ" value={data.participants ?? 0} />
          <Metric label="Chưa hoàn tất" value={data.awaiting_completion ?? 0} detail={`${data.finalized ?? 0} người đã chốt kết quả`} />
          <Metric label="Điểm trung bình hợp lệ" value={data.average ?? "—"} detail={`${data.sample_size ?? 0} kết quả hiện hành / đã chốt`} />
          <Metric label="KPI đã nhập thực tế" value={data.kpi_entry_percent != null ? `${data.kpi_entry_percent}%` : "—"} detail={`${data.kpis_entered ?? 0}/${data.kpis_assigned ?? 0} KPI đã giao; không phải tỷ lệ đạt mục tiêu`} /></div>
        {!data.selected_cycle || !data.participants ? <p className="empty-state">Chưa có người tham gia trong chu kỳ và phạm vi được phép. Bạn vẫn có thể mở hộp việc phản hồi của mình.</p> : <>
          <div className="feedback-cards"><section className="inbox-card" aria-labelledby="progress-title"><h2 id="progress-title">Tiến độ đánh giá</h2>
            <dl className="dashboard-list">{[["Chưa tính", data.not_calculated], ["Cần tính lại", data.stale], ["Hiện hành, chưa chốt", data.current], ["Đã chốt", data.finalized]].map(([label, value]) => <div key={String(label)}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
            <p className="help-text">Kết quả cần tính lại không được đưa vào điểm trung bình hoặc phân bố.</p>
            <Link href={`/review-cycles/${data.selected_cycle.id}`}>Mở chu kỳ để tiếp tục công việc →</Link>
          </section><section className="inbox-card" aria-labelledby="bands-title"><h2 id="bands-title">Phân bố điểm hợp lệ</h2>
            <p>{data.sample_size ?? 0} mẫu trong phạm vi được phép.</p>
            {!data.sample_size ? <p>Chưa có điểm hợp lệ để thống kê.</p> : <ul className="dashboard-bars">{Object.entries(data.score_bands ?? {}).map(([band, count]) => <li key={band}><div><span>{band} điểm</span><strong>{count} người</strong></div><progress max={data.sample_size} value={count} aria-label={`${band} điểm: ${count} người`} /></li>)}</ul>}
          </section></div>
          <section className="inbox-card dashboard-departments" aria-labelledby="departments-title"><h2 id="departments-title">Kết quả theo phòng ban</h2>
            <p className="help-text">{data.selected_cycle.status === "DRAFT" ? "Xem trước theo cơ cấu hiện tại của chu kỳ nháp." : "Phòng ban được ghi nhận lúc kích hoạt chu kỳ; quyền xem theo cơ cấu hiện tại."} Chỉ sử dụng kết quả hợp lệ, hiển thị số mẫu của từng nhóm.</p>
            <div className="table-scroll"><table><thead><tr><th scope="col">Phòng ban</th><th scope="col">Tham gia</th><th scope="col">Số mẫu hợp lệ</th><th scope="col">Điểm trung bình</th></tr></thead><tbody>{data.departments?.map((item, index) => <tr key={`${item.name}-${index}`}><th scope="row">{item.name}</th><td>{item.participants}</td><td>{item.sample_size}</td><td>{item.average ?? "—"}</td></tr>)}</tbody></table></div>
            {data.departments_truncated && <p>Hiển thị tối đa 100 nhóm phòng ban.</p>}
          </section>
        </>}
      </>}
    </>}
  </section>;
}
