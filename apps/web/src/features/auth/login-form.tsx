"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "./auth-provider";
import { ApiClientError } from "../../lib/api-client";
import { demoRoles } from "./demo-accounts";

const schema = z.object({
  email: z.email("Nhập địa chỉ email hợp lệ."),
  password: z.string().min(1, "Nhập mật khẩu.").max(128, "Mật khẩu quá dài."),
});

export function safeRedirect(value: string | null): string {
  return value?.startsWith("/") && !value.startsWith("//") && !value.includes("\\") &&
    !/[\u0000-\u0020]/.test(value) ? value : "/dashboard";
}

export function LoginForm({ demoEnabled = true }: { demoEnabled?: boolean }) {
  const auth = useAuth();
  const router = useRouter();
  const search = useSearchParams();
  const target = safeRedirect(search.get("next"));
  const [error, setError] = useState("");
  const [demo, setDemo] = useState(demoEnabled);
  const [selectedRole, setSelectedRole] = useState<string>("HR");
  const role = demoRoles.find((item) => item.id === selectedRole)!;
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema),
    defaultValues: { email: demoEnabled ? demoRoles[0].accounts[0].email : "", password: "" },
  });
  const email = useWatch({ control: form.control, name: "email" });
  const busy = auth.login.isPending || form.formState.isSubmitting;
  const selectAccount = (email: string) => {
    form.setValue("email", email, { shouldValidate: true });
    setError("");
  };
  useEffect(() => { if (auth.user) router.replace(target); }, [auth.user, router, target]);

  if (auth.pending || auth.user) return <p role="status">Đang kiểm tra phiên đăng nhập…</p>;
  return <section className="auth-card login-card" aria-labelledby="login-title">
    <p className="eyebrow">INSIGHTHR · KHÔNG GIAN LÀM VIỆC</p>
    <h1 id="login-title">{demo ? "Trải nghiệm InsightHR" : "Đăng nhập tài khoản"}</h1>
    <p>{demo ? "Chọn vai trò để bắt đầu khám phá quy trình đánh giá nhân viên." : "Dùng email và mật khẩu do quản trị viên cấp."}</p>
    {demo && <div className="demo-role-grid" role="group" aria-label="Chọn vai trò demo">
      {demoRoles.map((item) => <button key={item.id} type="button" className="demo-role" aria-pressed={item.id === selectedRole} disabled={busy}
        onClick={() => { setSelectedRole(item.id); selectAccount(item.accounts[0].email); }}>
        <strong>{item.label}</strong><span>{item.description}</span>
      </button>)}
    </div>}
    <form onSubmit={form.handleSubmit(async (values) => {
      setError("");
      try { await auth.login.mutateAsync(values); router.replace(target); }
      catch (error) { setError(error instanceof ApiClientError && error.code === "login_rate_limited"
        ? "Đã thử đăng nhập quá nhiều lần. Vui lòng chờ ít phút rồi thử lại."
        : error instanceof ApiClientError && error.code === "login_temporarily_unavailable"
          ? "Đăng nhập tạm thời chưa khả dụng. Vui lòng thử lại sau."
          : "Email hoặc mật khẩu không đúng."); }
    })}>
      {demo ? <>
        {role.accounts.length > 1 && <><label htmlFor="demo-account">Người dùng thử</label>
          <select id="demo-account" disabled={busy} {...form.register("email")} value={email} onChange={(event) => selectAccount(event.target.value)}>
            {role.accounts.map((account) => <option key={account.email} value={account.email}>{account.name}</option>)}
          </select></>}
        {role.accounts.length === 1 && <input type="hidden" {...form.register("email")} />}
        <p className="demo-account-hint">Tài khoản đã chọn: <span>{email}</span></p>
      </> : <><label htmlFor="email">Email</label>
        <input id="email" type="email" autoComplete="username" {...form.register("email")} disabled={busy} /></>}
      {form.formState.errors.email && <p role="alert">{form.formState.errors.email.message}</p>}
      <label htmlFor="password">Mật khẩu</label>
      <input id="password" type="password" autoComplete="current-password" aria-describedby={demo ? "demo-password-help" : undefined} {...form.register("password")} disabled={busy} />
      {demo && <p id="demo-password-help" className="help-text">Nhập mật khẩu demo đã được cấp. Các tài khoản mẫu dùng chung mật khẩu lúc nạp dữ liệu, trừ khi đã đổi riêng.</p>}
      {form.formState.errors.password && <p role="alert">{form.formState.errors.password.message}</p>}
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={busy}>
        {busy ? "Đang đăng nhập…" : demo ? `Vào trải nghiệm · ${role.label}` : "Đăng nhập"}
      </button>
    </form>
    <button type="button" className="login-mode-switch" disabled={busy} onClick={() => {
      setDemo(!demo); setError(""); form.clearErrors();
      form.setValue("email", demo ? "" : role.accounts[0].email);
    }}>{demo ? "Dùng tài khoản riêng" : "Chọn tài khoản demo"}</button>
    <div className="login-footer"><span>Quên mật khẩu? Liên hệ người phụ trách demo.</span><Link href="/">Trạng thái hệ thống</Link></div>
  </section>;
}
