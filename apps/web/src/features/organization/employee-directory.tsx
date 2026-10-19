"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { organizationApi } from "./api";
import { EmployeeForm, ReferencePicker } from "./employee-form";
import { OrganizationAccess, Pagination } from "./shared";

export function EmployeeDirectory() {
  return <OrganizationAccess><Directory /></OrganizationAccess>;
}

function Directory() {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const query = useQuery({ queryKey: ["organization", "employees", page, q, department, status], queryFn: () => organizationApi.employees({
    page, page_size: 20, q, department_id: department, employment_status: status,
  }) });
  return <>
    <section className="auth-card wide"><p className="eyebrow">TỔ CHỨC · NHÂN SỰ</p>
      <div className="section-heading"><h1>Danh sách nhân viên</h1>{user?.role === "HR" && <button onClick={() => setCreating(!creating)}>{creating ? "Đóng form" : "Thêm nhân viên"}</button>}</div>
      {user?.role !== "HR" && <p>{user?.employee_id ? "Bạn đang xem hồ sơ thuộc phạm vi được phép." : "Tài khoản chưa liên kết hồ sơ nhân viên. Hãy liên hệ HR."}</p>}
      <form className="filters" onSubmit={(event) => {
        event.preventDefault(); const data = new FormData(event.currentTarget);
        setQ(String(data.get("q") ?? "").trim()); setStatus(String(data.get("status") ?? "")); setPage(1);
      }}><div><label htmlFor="employee-search">Tìm nhân viên</label><input id="employee-search" name="q" maxLength={100} placeholder="Mã hoặc họ tên" /></div>
        <div><label htmlFor="employee-status-filter">Trạng thái làm việc</label><select id="employee-status-filter" name="status"><option value="">Tất cả</option><option value="ACTIVE">Đang làm việc</option><option value="INACTIVE">Ngừng làm việc</option></select></div>
        <button type="submit">Tìm kiếm</button></form>
      <div className="directory-reference-filter"><ReferencePicker kind="departments" value={department} onChange={(value) => { setDepartment(value); setPage(1); }} labelOverride="Lọc phòng ban" activeOnly={false} /></div>
      {query.isPending && <p role="status">Đang tải nhân viên…</p>}
      {query.isError && <div role="alert"><p>Không thể tải danh sách nhân viên.</p><button onClick={() => { void query.refetch(); }}>Thử lại</button></div>}
      {query.data && <>
        {!query.data.items.length && <p>Không có nhân viên phù hợp.</p>}
        <div className="table-scroll"><table><caption>{query.data.total} nhân viên</caption><thead><tr><th>Mã nhân viên</th><th>Họ và tên</th><th>Phòng ban</th><th>Chức danh</th><th>Trạng thái</th></tr></thead>
          <tbody>{query.data.items.map((row) => <tr key={row.id}><td>{row.employee_code}</td><td><Link href={`/employees/${row.id}`}>{row.display_name}</Link></td>
            <td>{row.department_name}</td><td>{row.position_title}</td><td><span className={row.employment_status === "ACTIVE" ? "badge active" : "badge"}>{row.employment_status === "ACTIVE" ? "Đang làm việc" : "Ngừng làm việc"}</span></td></tr>)}</tbody></table></div>
        <Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} />
      </>}
    </section>
    {creating && user?.role === "HR" && <EmployeeForm onSaved={() => setCreating(false)} />}
  </>;
}
