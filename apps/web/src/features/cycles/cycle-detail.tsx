"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { organizationApi } from "../organization/api";
import { Pagination } from "../organization/shared";
import { reviewApi, type Cycle } from "./api";
import { CycleForm, type CycleValues } from "./cycle-directory";
import { cycleStatus, ReviewAccess, ReviewError } from "./shared";

export function CycleDetail({ id }: { id: string }) { return <ReviewAccess><Detail id={id} /></ReviewAccess>; }
function Detail({ id }: { id: string }) {
  const cache = useQueryClient();
  const [page, setPage] = useState(1), [q, setQ] = useState("");
  const [confirmation, setConfirmation] = useState<number | null>(null), [generation, setGeneration] = useState(0);
  const cycle = useQuery({queryKey: ["reviews", "cycle", id], queryFn: () => reviewApi.cycle(id)});
  const participants = useQuery({queryKey: ["reviews", "participants", id, page, q], queryFn: () => reviewApi.participants(id, {page, q}), enabled: !!cycle.data});
  const refresh = () => cache.invalidateQueries({queryKey: ["reviews"]});
  const edit = useMutation({mutationFn: (v: CycleValues) => reviewApi.saveCycle(id, v), onSuccess: async () => { await refresh(); setGeneration((v) => v + 1); }});
  const activate = useMutation({mutationFn: (version: number) => reviewApi.activate(id, version), onSuccess: () => {setConfirmation(null); void refresh();}});
  const remove = useMutation({mutationFn: (row: string) => reviewApi.remove(id, row, cycle.data!.version), onSuccess: () => {void refresh();}});
  if (cycle.isPending) return <p role="status">Đang tải chu kỳ…</p>;
  if (cycle.isError) return <ReviewError error={cycle.error} reload={() => {void cycle.refetch();}} />;
  const row = cycle.data;
  return <>
    <section className="auth-card wide"><Link href="/review-cycles">← Danh sách chu kỳ</Link><p className="eyebrow">{cycleStatus[row.status]}</p><h1>{row.name}</h1>
      <p>{row.start_date} – {row.end_date} · Phiên bản {row.version} · {row.participant_count} người tham gia trong phạm vi</p>
      <h2>{row.policy_is_preview ? "Cấu hình dự kiến khi kích hoạt" : "Cấu hình đã đóng băng"}</h2>
      <p>KPI: {row.policy.kpi_weight}% · Phản hồi: {row.policy.feedback_weight}% · Giới hạn điểm KPI: {row.policy.kpi_cap ?? "Không giới hạn"}</p>
      {row.policy_is_preview && <p>Cấu hình và tổ chức có thể thay đổi trước khi kích hoạt. Nhân viên và người quản lý cần có tài khoản đang hoạt động.</p>}
      <p>Chức năng tính điểm và chốt/đóng chu kỳ sẽ được bổ sung sau.</p>
      {row.can_activate && <button disabled={activate.isPending} onClick={() => setConfirmation(row.version)}>Kích hoạt chu kỳ</button>}
      {confirmation !== null && <section className="confirmation" role="group" aria-label="Xác nhận kích hoạt">
        <p>Kích hoạt sẽ đóng băng danh sách, phòng ban, chức danh, quan hệ quản lý và cấu hình chấm điểm. Sau đó không sửa danh sách tham gia.</p>
        <button disabled={activate.isPending} onClick={() => activate.mutate(confirmation)}>Xác nhận kích hoạt</button><button className="secondary" onClick={() => setConfirmation(null)}>Hủy</button>
      </section>}
      {activate.isError && <ReviewError error={activate.error} reload={() => {setConfirmation(null); void refresh();}} />}
    </section>
    {row.can_edit && <section className="auth-card"><h2>Thông tin bản nháp</h2><CycleForm key={generation} initial={row} pending={edit.isPending} onSave={(v) => edit.mutate(v)} />
      {edit.isError && <ReviewError error={edit.error} reload={() => {void cycle.refetch().then(() => setGeneration((v) => v + 1));}} />}</section>}
    {row.can_edit && <Enrollment cycle={row} />}
    <section className="auth-card wide"><h2>Người tham gia</h2>
      <form className="filters" onSubmit={(e) => {e.preventDefault(); setQ(String(new FormData(e.currentTarget).get("q") ?? "")); setPage(1);}}><label htmlFor="participant-search">Tìm người tham gia</label><input id="participant-search" name="q" maxLength={100} /><button>Tìm</button></form>
      {participants.isPending && <p role="status">Đang tải người tham gia…</p>}{participants.isError && <ReviewError error={participants.error} />}
      {participants.data && <><div className="table-scroll"><table><caption>{participants.data.total} người tham gia trong phạm vi</caption><thead><tr><th>Nhân viên</th><th>Phòng ban</th><th>Chức danh</th><th>Thao tác</th></tr></thead><tbody>
        {participants.data.items.map((p) => <tr key={p.id}><td>{p.employee_code} · {p.display_name}</td><td>{p.department_name}</td><td>{p.position_title}</td><td>{row.can_edit
          ? <button className="secondary" disabled={remove.isPending} onClick={() => remove.mutate(p.id)}>Bỏ {p.employee_code} khỏi nháp</button>
          : <Link href={`/employees/${p.employee_id}/kpis?cycle_id=${id}`}>{p.can_manage_kpis ? "Quản lý KPI" : "Xem KPI"}</Link>}</td></tr>)}</tbody></table></div>
        {!participants.data.items.length && <p>Chưa có người tham gia phù hợp.</p>}
        <Pagination page={page} total={participants.data.total} pending={participants.isFetching} onPage={setPage} /></>}
      {remove.isError && <ReviewError error={remove.error} reload={() => {void refresh();}} />}
    </section>
  </>;
}

function Enrollment({ cycle }: {cycle: Cycle}) {
  const cache = useQueryClient();
  const [page, setPage] = useState(1), [q, setQ] = useState("");
  const [selected, setSelected] = useState<Record<string, string>>({});
  const employees = useQuery({queryKey: ["organization", "cycle-enroll", cycle.id, page, q], queryFn: () => organizationApi.employees({page, q, employment_status: "ACTIVE"})});
  const mutation = useMutation({mutationFn: () => reviewApi.enroll(cycle.id, cycle.version, Object.keys(selected)), onSuccess: () => {setSelected({}); void cache.invalidateQueries({queryKey: ["reviews"]});}});
  const count = Object.keys(selected).length;
  return <section className="auth-card wide"><h2>Thêm người tham gia bản nháp</h2>
    <form className="filters" onSubmit={(e) => {e.preventDefault(); setQ(String(new FormData(e.currentTarget).get("q") ?? "")); setPage(1);}}><label htmlFor="enroll-search">Tìm nhân viên để thêm</label><input id="enroll-search" name="q" maxLength={100} /><button>Tìm nhân viên</button></form>
    {employees.isPending && <p role="status">Đang tải nhân viên…</p>}{employees.isError && <ReviewError error={employees.error} />}
    {employees.data && <>{employees.data.items.map((e) => <label className="checkbox-label" key={e.id}><input type="checkbox" checked={!!selected[e.id]} disabled={mutation.isPending || (!selected[e.id] && count >= 100)} onChange={(event) => {
      setSelected((previous) => {const next = {...previous}; if (event.target.checked) next[e.id] = e.display_name; else delete next[e.id]; return next;});
    }} />{e.employee_code} · {e.display_name}</label>)}
      {!employees.data.items.length && <p>Không có nhân viên phù hợp.</p>}
      <Pagination page={page} total={employees.data.total} pending={employees.isFetching} onPage={setPage} /></>}
    <p>Đã chọn {count}/100 người trong lượt này, giữ lựa chọn khi đổi trang. Chỉ chọn người chưa tham gia.</p>
    {count > 0 && <p>{Object.values(selected).join(", ")}</p>}
    <button disabled={!count || mutation.isPending} onClick={() => mutation.mutate()}>Thêm người đã chọn</button>
    {mutation.isError && <ReviewError error={mutation.error} reload={() => {void cache.invalidateQueries({queryKey: ["reviews"]});}} />}
  </section>;
}
