"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { authApi } from "./api";

const schema = z.object({
  old_password: z.string().min(1, "Nhập mật khẩu hiện tại."),
  new_password: z.string().min(12, "Mật khẩu cần 12–128 ký tự.").max(128, "Mật khẩu cần 12–128 ký tự."),
  confirmation: z.string(),
}).refine((value) => value.new_password === value.confirmation, {
  path: ["confirmation"], message: "Mật khẩu xác nhận không khớp.",
}).refine((value) => value.new_password !== value.old_password, {
  path: ["new_password"], message: "Mật khẩu mới phải khác mật khẩu hiện tại.",
});

export function ChangePasswordForm() {
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const mutation = useMutation({ mutationFn: authApi.changePassword });
  return <section className="auth-card" aria-labelledby="password-title">
    <h2 id="password-title">Đổi mật khẩu</h2>
    <p>Các phiên đăng nhập khác sẽ được đăng xuất sau khi đổi mật khẩu.</p>
    <form onSubmit={form.handleSubmit(async ({ old_password, new_password }) => {
      try { await mutation.mutateAsync({ old_password, new_password }); form.reset(); } catch { /* shown below */ }
    })}>
      <label htmlFor="old-password">Mật khẩu hiện tại</label>
      <input id="old-password" type="password" autoComplete="current-password" {...form.register("old_password")} />
      <label htmlFor="new-password">Mật khẩu mới</label>
      <input id="new-password" type="password" autoComplete="new-password" {...form.register("new_password")} />
      <label htmlFor="confirmation">Xác nhận mật khẩu mới</label>
      <input id="confirmation" type="password" autoComplete="new-password" {...form.register("confirmation")} />
      {Object.entries(form.formState.errors).map(([key, error]) => <p role="alert" key={key}>{error.message}</p>)}
      {mutation.isError && <p role="alert">Không thể đổi mật khẩu. Kiểm tra mật khẩu hiện tại và thử lại.</p>}
      {mutation.isSuccess && <p role="status">Đã đổi mật khẩu thành công.</p>}
      <button disabled={mutation.isPending} type="submit">{mutation.isPending ? "Đang lưu…" : "Đổi mật khẩu"}</button>
    </form>
  </section>;
}
