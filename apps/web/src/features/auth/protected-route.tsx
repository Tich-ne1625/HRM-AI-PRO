"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "./auth-provider";
import type { UserRole } from "./types";

export function ProtectedRoute({ children, roles }: { children: ReactNode; roles?: UserRole[] }) {
  const auth = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!auth.pending && !auth.user && !auth.error) router.replace("/login");
  }, [auth.pending, auth.user, auth.error, router]);
  if (auth.pending) return <p role="status">Đang kiểm tra phiên đăng nhập…</p>;
  if (auth.error) return <div role="alert">
    <p>Không thể kết nối để xác nhận phiên đăng nhập.</p>
    <button onClick={auth.retry}>Thử lại</button>
  </div>;
  if (!auth.user) return <p role="status">Đang chuyển đến trang đăng nhập…</p>;
  if (roles && !roles.includes(auth.user.role)) return <p role="alert">Bạn không có quyền truy cập trang này.</p>;
  return children;
}
