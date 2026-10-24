"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../auth/auth-provider";
import { Pagination } from "../organization/shared";
import { reviewApi, type Cycle } from "./api";
import { cycleStatus, ReviewAccess, ReviewError } from "./shared";

const cycleSchema = z.object({ name: z.string().trim().min(1, "Nhập tên chu kỳ.").max(200),
  start_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Chọn ngày bắt đầu."),
  end_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Chọn ngày kết thúc."),
}).refine((v) => v.start_date <= v.end_date, { message: "Ngày kết thúc phải từ ngày bắt đầu trở đi.", path: ["end_date"] });
export type CycleValues = z.infer<typeof cycleSchema> & { expected_version?: number };
export function CycleForm({ initial, pending, onSave }: { initial?: Cycle; pending: boolean; onSave: (values: CycleValues) => void }) {
  const [version] = useState(initial?.version);
  const form = useForm<z.infer<typeof cycleSchema>>({ resolver: zodResolver(cycleSchema), defaultValues: {
    name: initial?.name ?? "", start_date: initial?.start_date ?? "", end_date: initial?.end_date ?? "",
  } });
  return <form onSubmit={form.handleSubmit((values) => onSave({ ...values, ...(version ? {expected_version: version} : {}) }))}>
    <label htmlFor="cycle-name">Tên chu kỳ</label><input id="cycle-name" maxLength={200} {...form.register("name")} />
    <div className="form-grid"><div><label htmlFor="cycle-start">Ngày bắt đầu</label><input id="cycle-start" type="date" {...form.register("start_date")} /></div>
      <div><label htmlFor="cycle-end">Ngày kết thúc</label><input id="cycle-end" type="date" {...form.register("end_date")} /></div></div>
    {Object.entries(form.formState.errors).map(([key, error]) => <p key={key} role="alert">{error.message}</p>)}
    <button disabled={pending}>{pending ? "Đang lưu…" : initial ? "Lưu thông tin chu kỳ" : "Tạo chu kỳ nháp"}</button>
  </form>;
}
export function CycleDirectory() { return <ReviewAccess><Directory /></ReviewAccess>; }
function Directory() {
  const { user } = useAuth();
  const cache = useQueryClient();
  const [page, setPage] = useState(1), [q, setQ] = useState(""), [status, setStatus] = useState("");
  const [generation, setGeneration] = useState(0);
  const query = useQuery({ queryKey: ["reviews", "cycles", page, q, status], queryFn: () => reviewApi.cycles({page, q, status}) });
  const create = useMutation({ mutationFn: (values: CycleValues) => reviewApi.saveCycle(null, values), onSuccess: () => {
    setGeneration((v) => v + 1); void cache.invalidateQueries({queryKey: ["reviews"]});
  } });
  return <>
    <section className="auth-card wide"><p className="eyebrow">ĐÁNH GIÁ NHÂN SỰ</p><h1>Chu kỳ đánh giá</h1>
      <p>Mỗi lần chỉ có một chu kỳ đang đánh giá. HR chốt kết quả từng nhân viên trước khi đóng kỳ và kích hoạt chu kỳ tiếp theo.</p>
      <form className="filters" onSubmit={(e) => { e.preventDefault(); const data = new FormData(e.currentTarget); setQ(String(data.get("q") ?? "")); setStatus(String(data.get("status") ?? "")); setPage(1); }}>
        <div><label htmlFor="cycles-search">Tìm chu kỳ</label><input id="cycles-search" name="q" maxLength={100} /></div>
        <div><label htmlFor="cycles-status">Trạng thái chu kỳ</label><select id="cycles-status" name="status"><option value="">Tất cả</option>{Object.entries(cycleStatus).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></div><button>Lọc</button>
      </form>
      {query.isPending && <p role="status">Đang tải chu kỳ…</p>}{query.isError && <ReviewError error={query.error} reload={() => { void query.refetch(); }} />}
      {!query.isError && query.data && <><div className="table-scroll" tabIndex={0} role="region" aria-label="Chu kỳ đánh giá, có thể cuộn ngang"><table><caption>{query.data.total} chu kỳ trong phạm vi của bạn</caption><thead><tr><th>Tên</th><th>Thời gian</th><th>Trạng thái</th><th>Người tham gia</th></tr></thead><tbody>
        {query.data.items.map((row) => <tr key={row.id}><td><Link href={`/review-cycles/${row.id}`}>{row.name}</Link></td><td>{row.start_date} – {row.end_date}</td><td>{cycleStatus[row.status]}</td><td>{row.participant_count}</td></tr>)}</tbody></table></div>
        {!query.data.items.length && <p>Chưa có chu kỳ phù hợp trong phạm vi của bạn.</p>}
        <Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} /></>}
    </section>
    {user?.role === "HR" && <section className="auth-card"><h2>Tạo chu kỳ nháp</h2><CycleForm key={generation} pending={create.isPending} onSave={(v) => create.mutate(v)} />{create.isError && <ReviewError error={create.error} />}</section>}
  </>;
}
