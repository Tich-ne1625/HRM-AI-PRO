import Link from "next/link";
import type { Activity } from "./api";

const labels: Record<string, string> = { "user.created": "Đã tạo tài khoản", "user.role_changed": "Đã cập nhật vai trò tài khoản", "user.status_changed": "Đã cập nhật trạng thái tài khoản", "performance.calculated": "Đã tính điểm đánh giá", "performance.finalized": "Đã chốt kết quả đánh giá" };

export function RecentActivities({ items, admin }: { items: Activity[]; admin: boolean }) {
  return <section className="inbox-card recent-activities" aria-labelledby="activity-title"><h2 id="activity-title">Hoạt động gần đây</h2><p className="help-text">{admin ? "Tối đa 6 cập nhật tài khoản gần nhất." : "Tối đa 6 lần tính điểm / chốt kết quả trong chu kỳ và phạm vi đang xem."}</p>
    {!items.length ? <p>Chưa có hoạt động phù hợp trong phạm vi này.</p> : <ol className="activity-list">{items.filter((item) => labels[item.action]).map((item) => <li key={item.id}><div><strong>{labels[item.action]}</strong>{item.employee_id && item.cycle_id && <Link href={`/employees/${item.employee_id}/performance?cycle_id=${encodeURIComponent(item.cycle_id)}`}>{item.display_name} →</Link>}</div><time dateTime={item.occurred_at}>{new Date(item.occurred_at).toLocaleString("vi-VN")}</time></li>)}</ol>}
  </section>;
}
