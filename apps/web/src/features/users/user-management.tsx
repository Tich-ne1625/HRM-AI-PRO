"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiClientError } from "../../lib/api-client";
import { useAuth } from "../auth/auth-provider";
import type { CurrentUser, UserRole } from "../auth/types";
import { usersApi } from "./users-api";

const roles = ["ADMIN", "HR", "MANAGER", "EMPLOYEE"] as const;
const schema = z.object({ email: z.email("Email không hợp lệ."),
  password: z.string().min(12, "Mật khẩu cần 12–128 ký tự.").max(128, "Mật khẩu cần 12–128 ký tự."),
  role: z.enum(roles),
});
function message(error: Error | null): string {
  if (error instanceof ApiClientError) {
    if (error.code === "email_already_exists") return "Email này đã có tài khoản.";
    if (error.code === "last_active_admin") return "Không thể thay đổi ADMIN còn hoạt động cuối cùng.";
  }
  return "Không thể lưu thay đổi. Vui lòng kiểm tra dữ liệu và thử lại.";
}

export function UserManagement() {
  const auth = useAuth();
  // Keep hooks inside the authorized subtree so no users query is sent for other roles.
  if (auth.user?.role !== "ADMIN") return <p role="alert">Bạn không có quyền quản lý tài khoản.</p>;
  return <AdminUsers />;
}

function AdminUsers() {
  const [page, setPage] = useState(1);
  const [confirm, setConfirm] = useState<CurrentUser | null>(null);
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ["users", page], queryFn: () => usersApi.list(page) });
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema),
    defaultValues: { email: "", password: "", role: "EMPLOYEE" },
  });
  const create = useMutation({ mutationFn: usersApi.create, onSuccess: () => {
    form.reset(); void cache.invalidateQueries({ queryKey: ["users"] });
  } });
  const update = useMutation({ mutationFn: ({ id, values }: {
    id: string; values: { role?: UserRole; is_active?: boolean };
  }) => usersApi.update(id, values), onSuccess: () => {
    setConfirm(null); void cache.invalidateQueries({ queryKey: ["users"] });
    void cache.invalidateQueries({ queryKey: ["auth"] });
    void cache.invalidateQueries({ queryKey: ["feedback"] });
    void cache.invalidateQueries({ queryKey: ["performance"] });
    void cache.invalidateQueries({ queryKey: ["ai"] });
  } });
  return <>
    <section className="auth-card wide">
      <p className="eyebrow">QUẢN TRỊ HỆ THỐNG</p><h1>Quản lý tài khoản</h1>
      <p>Cấp quyền truy cập và quản lý trạng thái tài khoản.</p>
      {query.isPending && <p role="status">Đang tải tài khoản…</p>}
      {query.isError && <div role="alert"><p>Không thể tải tài khoản.</p>
        <button onClick={() => { void query.refetch(); }}>Thử lại</button></div>}
      {!query.isError && query.data && <>
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Tài khoản, có thể cuộn ngang"><table><caption>Danh sách tài khoản · {query.data.total} tài khoản</caption>
          <thead><tr><th>Email</th><th>Vai trò</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
          <tbody>{query.data.items.map((user) => <tr key={user.id}>
            <td>{user.email}</td><td><select aria-label={`Vai trò của ${user.email}`} value={user.role}
              disabled={update.isPending} onChange={(event) => update.mutate({
                id: user.id, values: { role: event.target.value as UserRole },
              })}>{roles.map((role) => <option key={role}>{role}</option>)}</select></td>
            <td><span className={user.is_active ? "badge active" : "badge"}>{user.is_active ? "Hoạt động" : "Đã vô hiệu hóa"}</span></td>
            <td><button className="secondary" aria-label={`${user.is_active ? "Vô hiệu hóa" : "Kích hoạt"} ${user.email}`}
              disabled={update.isPending} onClick={() => {
                if (user.is_active) setConfirm(user);
                else update.mutate({ id: user.id, values: { is_active: true } });
              }}>{user.is_active ? "Vô hiệu hóa" : "Kích hoạt"}</button></td>
          </tr>)}</tbody></table></div>
        <nav className="pagination" aria-label="Phân trang tài khoản">
          <button className="secondary" disabled={page === 1 || query.isFetching} onClick={() => setPage(page - 1)}>Trang trước</button>
          <span>Trang {page}</span>
          <button className="secondary" disabled={page * 20 >= query.data.total || query.isFetching} onClick={() => setPage(page + 1)}>Trang sau</button>
        </nav>
      </>}
      {confirm && <div role="alertdialog" aria-modal="false" aria-label="Xác nhận vô hiệu hóa" className="confirmation">
        <p>Vô hiệu hóa {confirm.email}? Tất cả phiên của tài khoản này sẽ kết thúc.</p>
        <button disabled={update.isPending} onClick={() => update.mutate({ id: confirm.id, values: { is_active: false } })}>Xác nhận vô hiệu hóa</button>
        <button className="secondary" onClick={() => setConfirm(null)}>Hủy</button>
      </div>}
      {update.isError && <p role="alert">{message(update.error)}</p>}
    </section>
    <section className="auth-card wide"><h2>Tạo tài khoản</h2>
      <form className="create-user-form" onSubmit={form.handleSubmit(async (values) => {
        try { await create.mutateAsync(values); } catch { /* shown below */ }
      })}>
        <div><label htmlFor="new-email">Email tài khoản mới</label><input id="new-email" type="email" autoComplete="off" {...form.register("email")} /></div>
        <div><label htmlFor="initial-password">Mật khẩu ban đầu</label><input id="initial-password" type="password" autoComplete="new-password" {...form.register("password")} /></div>
        <div><label htmlFor="new-role">Vai trò ban đầu</label><select id="new-role" {...form.register("role")}>{roles.map((role) => <option key={role}>{role}</option>)}</select></div>
        {Object.entries(form.formState.errors).map(([key, error]) => <p key={key} role="alert">{error.message}</p>)}
        {create.isError && <p role="alert">{message(create.error)}</p>}
        {create.isSuccess && <p role="status">Đã tạo tài khoản.</p>}
        <button disabled={create.isPending} type="submit">{create.isPending ? "Đang tạo…" : "Tạo tài khoản"}</button>
      </form>
    </section>
  </>;
}
