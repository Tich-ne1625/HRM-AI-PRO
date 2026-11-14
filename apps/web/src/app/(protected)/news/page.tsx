import { Suspense } from "react";
import { InternalFeed } from "../../../features/collaboration/feed";

export default function NewsPage() { return <Suspense fallback={<p>Đang mở bảng tin…</p>}><InternalFeed /></Suspense>; }
