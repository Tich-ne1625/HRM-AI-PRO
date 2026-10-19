"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { organizationApi } from "./api";
import { EmployeeForm } from "./employee-form";
import { OrganizationAccess, organizationError } from "./shared";

export function EmployeeDetail({ id }: { id: string }) {
  return <OrganizationAccess><Detail id={id} /></OrganizationAccess>;
}
function Detail({ id }: { id: string }) {
  const { user } = useAuth();
  const [editing, setEditing] = useState(false);
  const query = useQuery({ queryKey: ["organization", "employee", id], queryFn: () => organizationApi.employee(id) });
  if (query.isPending) return <p role="status">Đang tải hồ sơ…</p>;
  if (query.isError) return <div role="alert"><p>{organizationError(query.error)}</p><Link href="/employees">Về danh sách nhân viên</Link></div>;
  const row = query.data;
  return <>
    <section className="auth-card wide"><Link href="/employees">← Danh sách nhân viên</Link>
      <p className="eyebrow">HỒ SƠ NHÂN VIÊN · {row.employee_code}</p>
      <div className="section-heading"><h1>{row.display_name}</h1>{user?.role === "HR" && <button className="secondary" onClick={() => setEditing(!editing)}>{editing ? "Hủy chỉnh sửa" : "Chỉnh sửa hồ sơ"}</button>}</div>
      <dl className="detail-grid"><div><dt>Phòng ban</dt><dd>{row.department_name}</dd></div><div><dt>Chức danh</dt><dd>{row.position_title}</dd></div>
        <div><dt>Người quản lý</dt><dd>{row.manager_name ?? "Chưa có"}</dd></div><div><dt>Trạng thái làm việc</dt><dd>{row.employment_status === "ACTIVE" ? "Đang làm việc" : "Ngừng làm việc"}</dd></div>
        <div><dt>Tài khoản đăng nhập</dt><dd>{row.user_id ? "Đã liên kết" : "Chưa liên kết"}</dd></div></dl>
    </section>
    {editing && user?.role === "HR" && <EmployeeForm key={row.updated_at} initial={row} onSaved={() => setEditing(false)} />}
  </>;
}
