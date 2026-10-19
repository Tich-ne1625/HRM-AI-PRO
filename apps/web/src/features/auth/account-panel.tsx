"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "./auth-provider";
import { ChangePasswordForm } from "./change-password-form";

export function AccountPanel() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [error, setError] = useState("");
  if (!user) return null;
  return <>
    <section className="auth-card">
      <p className="eyebrow">TÀI KHOẢN CỦA BẠN</p><h1>Xin chào, {user.email}</h1>
      <dl><dt>Email</dt><dd>{user.email}</dd><dt>Vai trò</dt><dd>{user.role}</dd></dl>
      {user.role === "ADMIN" && <Link href="/admin/users">Quản lý tài khoản</Link>}
      <button className="secondary" disabled={logout.isPending} onClick={async () => {
        setError("");
        try { await logout.mutateAsync(); router.replace("/login"); }
        catch { setError("Chưa thể đăng xuất. Vui lòng thử lại."); }
      }}>Đăng xuất</button>
      {error && <p role="alert">{error}</p>}
    </section>
    <ChangePasswordForm />
  </>;
}
