"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "./auth-provider";
import { ApiClientError } from "../../lib/api-client";

const schema = z.object({
  email: z.email("Nhập địa chỉ email hợp lệ."),
  password: z.string().min(1, "Nhập mật khẩu.").max(128, "Mật khẩu quá dài."),
});

export function safeRedirect(value: string | null): string {
  return value?.startsWith("/") && !value.startsWith("//") && !value.includes("\\") &&
    !/[\u0000-\u0020]/.test(value) ? value : "/dashboard";
}

export function LoginForm() {
  const auth = useAuth();
  const router = useRouter();
  const search = useSearchParams();
  const target = safeRedirect(search.get("next"));
  const [error, setError] = useState("");
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  useEffect(() => { if (auth.user) router.replace(target); }, [auth.user, router, target]);

  if (auth.pending || auth.user) return <p role="status">Đang kiểm tra phiên đăng nhập…</p>;
  return <section className="auth-card" aria-labelledby="login-title">
    <p className="eyebrow">INSIGHTHR · KHÔNG GIAN LÀM VIỆC</p>
    <h1 id="login-title">Chào mừng trở lại</h1>
    <p>Đăng nhập bằng tài khoản do quản trị viên cấp.</p>
    <form onSubmit={form.handleSubmit(async (values) => {
      setError("");
      try { await auth.login.mutateAsync(values); router.replace(target); }
      catch (error) { setError(error instanceof ApiClientError && error.code === "login_rate_limited"
        ? "Đã thử đăng nhập quá nhiều lần. Vui lòng chờ ít phút rồi thử lại."
        : error instanceof ApiClientError && error.code === "login_temporarily_unavailable"
          ? "Đăng nhập tạm thời chưa khả dụng. Vui lòng thử lại sau."
          : "Email hoặc mật khẩu không đúng."); }
    })}>
      <label htmlFor="email">Email</label>
      <input id="email" type="email" autoComplete="username" {...form.register("email")} />
      {form.formState.errors.email && <p role="alert">{form.formState.errors.email.message}</p>}
      <label htmlFor="password">Mật khẩu</label>
      <input id="password" type="password" autoComplete="current-password" {...form.register("password")} />
      {form.formState.errors.password && <p role="alert">{form.formState.errors.password.message}</p>}
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={auth.login.isPending || form.formState.isSubmitting}>
        {auth.login.isPending ? "Đang đăng nhập…" : "Đăng nhập"}
      </button>
    </form>
    <p className="help-text">Quên mật khẩu? Liên hệ quản trị viên của bạn.</p>
    <Link href="/">Xem trạng thái hệ thống</Link>
  </section>;
}
