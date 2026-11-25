import { Suspense } from "react";
import { WorkWorkspace } from "../../../features/work-management/workspace";

export default function Page() {
  return <Suspense fallback={<p>Đang mở công việc…</p>}><WorkWorkspace /></Suspense>;
}
