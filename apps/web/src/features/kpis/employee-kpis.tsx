"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { reviewApi, type Allocation, type AllocationInput, type AllocationLine, type Definition } from "../cycles/api";
import { cycleStatus, decimalUnits, ReviewAccess, ReviewError } from "../cycles/shared";
import { Pagination } from "../organization/shared";
import { EvaluationTabs } from "../performance/context-tabs";

export function EmployeeKpis({id, cycle}: {id: string; cycle: string}) {
  return <ReviewAccess>{cycle ? <Detail id={id} cycle={cycle} /> : <section className="auth-card"><p>Hãy chọn chu kỳ và người tham gia để xem KPI.</p><Link href="/review-cycles">Chọn chu kỳ đánh giá</Link></section>}</ReviewAccess>;
}
function Detail({id, cycle}: {id: string; cycle: string}) {
  const cache = useQueryClient();
  const [editing, setEditing] = useState(false), [generation, setGeneration] = useState(0);
  const [editingActual, setEditingActual] = useState<{row: AllocationLine; version: number} | null>(null);
  const query = useQuery({queryKey: ["reviews", "allocation", id, cycle], queryFn: () => reviewApi.allocation(id, cycle)});
  const cycleQuery = useQuery({queryKey: ["reviews", "cycle", cycle], queryFn: () => reviewApi.cycle(cycle)});
  const refresh = async () => {await Promise.all(["reviews", "feedback", "performance", "ai"].map((key) => cache.invalidateQueries({queryKey: [key]})));};
  const replace = useMutation({mutationFn: ({version, items}: {version: number; items: AllocationInput[]}) => reviewApi.replace(id, cycle, version, items), onSuccess: async () => {setEditing(false); await refresh();}});
  const actual = useMutation({mutationFn: ({row, version, value}: {row: string; version: number; value: string | null}) => reviewApi.actual(row, version, value), onSuccess: async () => {setEditingActual(null); await refresh();}});
  if (query.isPending) return <p role="status">Đang tải KPI nhân viên…</p>;
  if (query.isError) return <ReviewError error={query.error} reload={() => {void query.refetch();}} />;
  const data = query.data, participant = data.participant;
  return <><section className="auth-card wide"><Link href={`/review-cycles/${cycle}`}>← Người tham gia chu kỳ</Link><p className="eyebrow">{cycleQuery.data?.name ?? "Chu kỳ được chọn"} · {cycleStatus[data.cycle_status]}</p>
    <h1>KPI · {participant.display_name}</h1><p>{participant.employee_code} · {participant.department_name} · {participant.position_title}</p>
    {participant.is_snapshot && <EvaluationTabs employeeId={id} cycleId={cycle} active="kpis" />}
    {cycleQuery.isError && <ReviewError error={cycleQuery.error} />}
    <p>{participant.is_snapshot ? "Thông tin tổ chức tại lúc kích hoạt chu kỳ." : "Thông tin nháp chưa đóng băng."} Phiên bản dữ liệu đánh giá: {participant.evidence_version}.</p>
    {!data.items.length && <p>Chưa phân bổ KPI.</p>}
    <div className="table-scroll"><table><caption>KPI được giao trong chu kỳ đang chọn</caption><thead><tr><th>KPI / hướng</th><th>Mục tiêu</th><th>Trọng số</th><th>Kết quả thực tế</th></tr></thead><tbody>{data.items.map((row) => <tr key={row.id}>
      <td>{row.definition.code} · {row.definition.name}<br />{row.definition.direction === "HIGHER_IS_BETTER" ? "Càng cao càng tốt" : "Càng thấp càng tốt"}</td><td>{row.target} {row.definition.unit}</td><td>{row.weight}%</td><td>
        <p>{row.actual === null ? "Chưa nhập" : row.actual}</p>
        {participant.can_manage_kpis && !editing && (editingActual?.row.id === row.id
          ? <><ActualForm key={row.id} row={editingActual.row} pending={actual.isPending} onSave={(value) => actual.mutate({row: row.id, version: editingActual.version, value})} /><button className="secondary" disabled={actual.isPending} onClick={() => {setEditingActual(null); actual.reset();}}>Hủy nhập thực tế</button></>
          : <button className="secondary" disabled={editingActual !== null || actual.isPending} onClick={() => {setEditingActual({row, version: participant.evidence_version}); actual.reset();}}>Nhập thực tế {row.definition.code}</button>)}
      </td></tr>)}</tbody></table></div>
    {actual.isError && <ReviewError error={actual.error} reload={() => {setEditingActual(null); actual.reset(); void refresh();}} />}
    {participant.can_manage_kpis && <button className="secondary" disabled={editingActual !== null || actual.isPending || replace.isPending} onClick={() => {setEditing(!editing); replace.reset(); setGeneration((v) => v + 1);}}>{editing ? "Hủy chỉnh phân bổ" : "Chỉnh phân bổ KPI"}</button>}
  </section>
  {editing && participant.can_manage_kpis && <section className="auth-card wide"><h2>Phân bổ trọn bộ KPI</h2>
    <AllocationEditor key={generation} initial={data} employee={id} cycle={cycle} pending={replace.isPending} onSave={(version, items) => replace.mutate({version, items})} />
    {replace.isError && <ReviewError error={replace.error} reload={() => {void query.refetch().then(() => {setGeneration((v) => v + 1); replace.reset();});}} />}
  </section>}</>;
}

const actualSchema = z.object({actual: z.string().refine((v) => v === "" || decimalUnits(v, 4, 10) !== null, "Nhập số không âm, tối đa 4 chữ số lẻ; để trống để xóa kết quả.")});
function ActualForm({row, pending, onSave}: {row: AllocationLine; pending: boolean; onSave: (value: string | null) => void}) {
  const form = useForm<z.infer<typeof actualSchema>>({resolver: zodResolver(actualSchema), defaultValues: {actual: row.actual ?? ""}});
  return <form onSubmit={form.handleSubmit((v) => onSave(v.actual === "" ? null : v.actual))}>
    <label htmlFor={`actual-${row.id}`}>Thực tế {row.definition.code}</label><input id={`actual-${row.id}`} inputMode="decimal" maxLength={15} {...form.register("actual")} />
    {form.formState.errors.actual && <p role="alert">{form.formState.errors.actual.message}</p>}
    <button disabled={pending}>Lưu thực tế {row.definition.code}</button>
  </form>;
}

const rowSchema = z.object({definition_id: z.string().min(1), label: z.string(), unit: z.string(), target: z.string().refine((v) => (decimalUnits(v, 4, 10) ?? 0) > 0, "Mục tiêu phải dương, tối đa 4 chữ số lẻ."),
  weight: z.string().refine((v) => {const units = decimalUnits(v, 2, 3); return units !== null && units > 0 && units <= 10000;}, "Trọng số phải trong (0,100], tối đa 2 chữ số lẻ.")});
const allocationSchema = z.object({items: z.array(rowSchema).min(1).max(100)}).superRefine((v, ctx) => {
  if (new Set(v.items.map((r) => r.definition_id)).size !== v.items.length || v.items.reduce((total, r) => total + (decimalUnits(r.weight, 2, 3) ?? 0), 0) !== 10000) ctx.addIssue({code: "custom", path: ["items"], message: "Không trùng KPI và tổng trọng số phải đúng 100.00%."});
});
type AllocationValues = z.infer<typeof allocationSchema>;
export function AllocationEditor({initial, employee, cycle, pending, onSave}: {initial: Allocation; employee: string; cycle: string; pending: boolean; onSave: (version: number, items: AllocationInput[]) => void}) {
  const [base] = useState(initial);
  const [confirmation, setConfirmation] = useState<AllocationInput[] | null>(null);
  const form = useForm<AllocationValues>({resolver: zodResolver(allocationSchema), defaultValues: {items: base.items.map((r) => ({definition_id: r.definition_id, label: `${r.definition.code} · ${r.definition.name}`, unit: r.definition.unit, target: r.target, weight: r.weight}))}});
  const array = useFieldArray({control: form.control, name: "items"});
  const values = useWatch({control: form.control, name: "items"}) ?? [];
  const units = values.map((r) => decimalUnits(r.weight ?? "", 2, 3));
  const sum = units.reduce<number>((total, value) => total + (value ?? 0), 0);
  const full = units.every((v) => v !== null && v > 0 && v <= 10000) && sum === 10000 && values.length > 0;
  function save(v: AllocationValues) {
    const items = v.items.map(({definition_id, target, weight}) => ({definition_id, target, weight}));
    const clears = base.items.some((old) => old.actual !== null && (!items.some((i) => i.definition_id === old.definition_id) || items.some((i) => i.definition_id === old.definition_id && decimalUnits(i.target, 4, 10) !== decimalUnits(old.target, 4, 10))));
    if (clears) setConfirmation(items); else onSave(base.participant.evidence_version, items);
  }
  function add(row: Definition) {
    if (array.fields.length < 100 && !values.some((v) => v.definition_id === row.id)) array.append({definition_id: row.id, label: `${row.code} · ${row.name}`, unit: row.unit, target: "", weight: ""});
  }
  return <>
    <p>Chỉnh sửa cả danh sách rồi lưu một lần. Tổng trọng số cần đúng 100.00%. Giới hạn 100 KPI.</p>
    <form onSubmit={form.handleSubmit(save)}><fieldset disabled={pending || confirmation !== null}>
      {array.fields.map((field, index) => <section className="confirmation" key={field.id}><h3>{field.label}</h3>
        <label htmlFor={`target-${field.id}`}>Mục tiêu {field.label} ({field.unit})</label><input id={`target-${field.id}`} inputMode="decimal" maxLength={15} {...form.register(`items.${index}.target`)} />
        <label htmlFor={`weight-${field.id}`}>Trọng số {field.label} (%)</label><input id={`weight-${field.id}`} inputMode="decimal" maxLength={6} {...form.register(`items.${index}.weight`)} />
        <button type="button" className="secondary" onClick={() => array.remove(index)}>Bỏ {field.label}</button>
        {form.formState.errors.items?.[index]?.target && <p role="alert">{form.formState.errors.items[index]?.target?.message}</p>}
      </section>)}
      <p role="status">Tổng trọng số: {(sum / 100).toFixed(2)}%</p>
      {!full && <p>Cần đủ 100.00% với từng trọng số dương để lưu.</p>}
      {form.formState.errors.items?.root && <p role="alert">{form.formState.errors.items.root.message}</p>}
      <button disabled={!full || pending}>Lưu toàn bộ phân bổ</button>
    </fieldset></form>
    {confirmation && <section className="confirmation" role="group" aria-label="Xác nhận thay đổi mục tiêu"><p>Thao tác này bỏ KPI hoặc thay mục tiêu có kết quả thực tế. Kết quả liên quan sẽ bị xóa để nhập lại.</p><button disabled={pending} onClick={() => onSave(base.participant.evidence_version, confirmation)}>Xác nhận lưu và xóa thực tế liên quan</button><button className="secondary" onClick={() => setConfirmation(null)}>Hủy xác nhận</button></section>}
    {!confirmation && <KpiOptions employee={employee} cycle={cycle} selected={values.map((v) => v.definition_id ?? "")} disabled={pending || values.length >= 100} onAdd={add} />}
  </>;
}
function KpiOptions({employee, cycle, selected, disabled, onAdd}: {employee: string; cycle: string; selected: string[]; disabled: boolean; onAdd: (row: Definition) => void}) {
  const [page, setPage] = useState(1), [q, setQ] = useState("");
  const query = useQuery({queryKey: ["reviews", "options", employee, cycle, page, q], queryFn: () => reviewApi.options(employee, cycle, {page, q})});
  return <section><h3>Chọn KPI đang sử dụng</h3><form className="filters" onSubmit={(e) => {e.preventDefault(); setQ(String(new FormData(e.currentTarget).get("q") ?? "")); setPage(1);}}><label htmlFor="options-search">Tìm KPI để gán</label><input id="options-search" name="q" maxLength={100} /><button>Tìm KPI</button></form>
    {query.isPending && <p role="status">Đang tải lựa chọn KPI…</p>}{query.isError && <ReviewError error={query.error} />}
    {query.data && <>{query.data.items.map((r) => <p key={r.id}>{r.code} · {r.name} ({r.unit}) <button className="secondary" disabled={disabled || selected.includes(r.id)} onClick={() => onAdd(r)}>Thêm {r.code}</button></p>)}
      {!query.data.items.length && <p>Không có KPI đang sử dụng phù hợp.</p>}<Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} /></>}
  </section>;
}
