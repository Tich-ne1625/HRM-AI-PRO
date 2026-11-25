"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "../workspace/detail-link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../auth/auth-provider";
import { Pagination } from "../organization/shared";
import { reviewApi, type Cycle } from "./api";
import { cycleStatus, ReviewAccess, ReviewError } from "./shared";
import { WorkspaceDialog } from "../workspace/dialog";

const cycleSchema = z.object({ name: z.string().trim().min(1, "Nhập tên chu kỳ.").max(200),
  start_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Chọn ngày bắt đầu."),
  end_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Chọn ngày kết thúc."),
}).refine((v) => v.start_date <= v.end_date, { message: "Ngày kết thúc phải từ ngày bắt đầu trở đi.", path: ["end_date"] });
export type CycleValues = z.infer<typeof cycleSchema> & { expected_version?: number };
export function CycleForm({ initial, pending, onSave }: { initial?: Cycle; pending: boolean; onSave: (values: CycleValues) => void }) {
  const [version] = useState(initial?.version);
  const [mode, setMode] = useState(initial?.workflow_mode ?? "LEGACY");
  const form = useForm<z.infer<typeof cycleSchema>>({ resolver: zodResolver(cycleSchema), defaultValues: {
    name: initial?.name ?? "", start_date: initial?.start_date ?? "", end_date: initial?.end_date ?? "",
  } });
  return <form onSubmit={(event) => {
    const data = new FormData(event.currentTarget);
    void form.handleSubmit((values) => {
      const schedule = mode === "CONTINUOUS" && !initial?.workflow_schedule_frozen ? {timezone: String(data.get("timezone")), ...Object.fromEntries(["acknowledgement_due_at", "input_cutoff_at", "verification_due_at", "response_due_at"].map((key) => [key, new Date(String(data.get(key))).toISOString()]))} : undefined;
      onSave({...values, ...(version ? {expected_version: version} : mode === "CONTINUOUS" ? {workflow_mode: mode} : {}), ...(schedule ? {workflow_schedule: schedule} : {})});
    })(event);
  }}>
    {!initial && <><label htmlFor="cycle-mode">Cách vận hành</label><select id="cycle-mode" value={mode} onChange={(e) => setMode(e.target.value as "LEGACY" | "CONTINUOUS")}><option value="LEGACY">Đánh giá kết quả (luồng hiện tại)</option><option value="CONTINUOUS">Quản lý theo tiến trình (kế hoạch & công việc)</option></select><p className="help-text">Chế độ được giữ cố định sau khi tạo chu kỳ.</p></>}
    <label htmlFor="cycle-name">Tên chu kỳ</label><input id="cycle-name" maxLength={200} {...form.register("name")} />
    <div className="form-grid"><div><label htmlFor="cycle-start">Ngày bắt đầu</label><input id="cycle-start" type="date" readOnly={initial?.workflow_schedule_frozen} {...form.register("start_date")} /></div>
      <div><label htmlFor="cycle-end">Ngày kết thúc</label><input id="cycle-end" type="date" readOnly={initial?.workflow_schedule_frozen} {...form.register("end_date")} /></div></div>
    {initial?.workflow_schedule_frozen && <p className="help-text">Lịch đã được dùng để thống nhất kế hoạch. Chỉ đổi tên kỳ; mốc thời gian được giữ cố định.</p>}
    {mode === "CONTINUOUS" && <fieldset disabled={initial?.workflow_schedule_frozen}><legend>Lịch điều phối theo tiến trình</legend><label htmlFor="workflow-zone">Múi giờ của kỳ</label><input id="workflow-zone" name="timezone" defaultValue={initial?.workflow_schedule?.timezone ?? "Asia/Ho_Chi_Minh"} required />{Object.entries({acknowledgement_due_at: "Hạn xác nhận kế hoạch (trước ngày bắt đầu)", input_cutoff_at: "Hạn nộp dữ liệu (sau ngày kết thúc)", verification_due_at: "Hạn xác minh", response_due_at: "Hạn giải trình"}).map(([key, label]) => {
      const value = initial?.workflow_schedule?.[key as "input_cutoff_at"];
      const local = value ? new Date(new Date(value).getTime() - new Date(value).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "";
      return <div key={key}><label htmlFor={key}>{label}</label><input id={key} name={key} type="datetime-local" required defaultValue={local} /></div>;
    })}<p className="help-text">Giờ nhập theo múi giờ máy của bạn; hệ thống lưu UTC. Múi giờ kỳ xác định ngày bắt đầu/kết thúc công việc.</p></fieldset>}
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
  const [creating, setCreating] = useState(false);
  const query = useQuery({ queryKey: ["reviews", "cycles", page, q, status], queryFn: () => reviewApi.cycles({page, q, status}) });
  const create = useMutation({ mutationFn: (values: CycleValues) => reviewApi.saveCycle(null, values), onSuccess: () => {
    setGeneration((v) => v + 1); setCreating(false); void cache.invalidateQueries({queryKey: ["reviews"]});
  } });
  return <>
    <section className="auth-card wide"><p className="eyebrow">ĐÁNH GIÁ NHÂN SỰ</p><div className="section-heading"><h1>Chu kỳ đánh giá</h1>{user?.role === "HR" && <button onClick={() => { create.reset(); setCreating(true); }}>Tạo chu kỳ mới</button>}</div>
      <p>{user?.role === "HR" ? "Tạo và theo dõi đợt đánh giá. Mở một chu kỳ để quản lý người tham gia và hoàn tất kết quả." : "Chọn chu kỳ để mở KPI, phản hồi và kết quả trong phạm vi của bạn."}</p>
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
    {creating && user?.role === "HR" && <WorkspaceDialog title="Tạo chu kỳ mới" close={() => setCreating(false)}><section className="auth-card"><CycleForm key={generation} pending={create.isPending} onSave={(v) => create.mutate(v)} />{create.isError && <ReviewError error={create.error} />}</section></WorkspaceDialog>}
  </>;
}
