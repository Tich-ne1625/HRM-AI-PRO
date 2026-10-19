import { Suspense } from "react";
import { LoginForm } from "../../../features/auth/login-form";

export default function LoginPage() {
  return <main className="auth-shell"><Suspense fallback={<p>Đang tải…</p>}><LoginForm /></Suspense></main>;
}
