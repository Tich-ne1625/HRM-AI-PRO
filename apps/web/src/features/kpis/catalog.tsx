"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../auth/auth-provider";
import { reviewApi, type Definition } from "../cycles/api";
import { ReviewAccess, ReviewError } from "../cycles/shared";
import { Pagination } from "../organization/shared";

const schema = z.object({
  code: z.string().trim().toUpperCase().regex(/^[A-Z0-9][A-Z0-9_-]{1,31}$/, "Mã gồm 2–32 ký tự chữ, số, gạch ngang hoặc gạch dưới."),
  name: z.string().trim().min(1, "Nhập tên KPI.").max(200),
  unit: z.string().trim().min(1, "Nhập đơn vị.").max(50), description: z.string().max(2000),
  direction: z.enum(["HIGHER_IS_BETTER", "LOWER_IS_BETTER"]),
});
type Values = z.infer<typeof schema>;
export function KpiCatalog() {return <ReviewAccess><Catalog /></ReviewAccess>;}
function Catalog() {
  const {user} = useAuth(), cache = useQueryClient();
  const hr = user?.role === "HR";
  const [page, setPage] = useState(1), [q, setQ] = useState(""), [status, setStatus] = useState("");
  const [editing, setEditing] = useState<Definition | null>(null), [retiring, setRetiring] = useState<Definition | null>(null), [generation, setGeneration] = useState(0);
  const query = useQuery({queryKey: ["reviews", "definitions", page, q, status], queryFn: () => reviewApi.definitions({page, q, ...(status ? {is_active: status === "true"} : {})})});
  const save = useMutation({mutationFn: ({row, values}: {row: Definition | null; values: Partial<Values> & {is_active?: boolean}}) => reviewApi.saveDefinition(row?.id ?? null, {...values, ...(row ? {expected_version: row.version} : {})}), onSuccess: () => {
    setEditing(null); setRetiring(null); setGeneration((v) => v + 1); void cache.invalidateQueries({queryKey: ["reviews"]});
  }});
  return <><section className="auth-card wide"><p className="eyebrow">KPI</p><h1>Danh mục KPI</h1>
    <p>Định nghĩa mô tả chỉ tiêu. KPI đã gán giữ bản sao tại lúc gán; sửa danh mục không thay đổi lịch sử.</p>
    {!hr && <p>Chỉ hiển thị định nghĩa đã gán trong phạm vi của bạn.</p>}
    <form className="filters" onSubmit={(e) => {e.preventDefault(); const data = new FormData(e.currentTarget); setQ(String(data.get("q") ?? "")); setStatus(String(data.get("status") ?? "")); setPage(1);}}>
      <div><label htmlFor="kpi-search">Tìm KPI</label><input id="kpi-search" name="q" maxLength={100} /></div>
      <div><label htmlFor="kpi-status">Trạng thái KPI</label><select id="kpi-status" name="status"><option value="">Tất cả</option><option value="true">Đang sử dụng</option><option value="false">Ngừng sử dụng</option></select></div><button>Lọc</button>
    </form>
    {query.isPending && <p role="status">Đang tải KPI…</p>}{query.isError && <ReviewError error={query.error} reload={() => {void query.refetch();}} />}
    {query.data && <><div className="table-scroll"><table><caption>{query.data.total} định nghĩa KPI</caption><thead><tr><th>Mã / tên</th><th>Đơn vị</th><th>Hướng đánh giá</th><th>Trạng thái</th>{hr && <th>Thao tác</th>}</tr></thead><tbody>{query.data.items.map((row) => <tr key={row.id}>
      <td>{row.code} · {row.name}</td><td>{row.unit}</td><td>{row.direction === "HIGHER_IS_BETTER" ? "Càng cao càng tốt" : "Càng thấp càng tốt"}</td><td>{row.is_active ? "Đang sử dụng" : "Ngừng sử dụng"}</td>
      {hr && <td className="row-actions"><button className="secondary" disabled={save.isPending} onClick={() => setEditing(row)}>Sửa {row.code}</button>
        <button className="secondary" disabled={save.isPending} onClick={() => row.is_active ? setRetiring(row) : save.mutate({row, values: {is_active: true}})}>{row.is_active ? "Ngừng sử dụng" : "Kích hoạt lại"} {row.code}</button></td>}</tr>)}</tbody></table></div>
      {!query.data.items.length && <p>Chưa có KPI phù hợp.</p>}<Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} /></>}
    {retiring && <section className="confirmation" role="group" aria-label="Xác nhận ngừng KPI"><p>Ngừng sử dụng {retiring.code}? KPI đã gán vẫn được giữ, không thể gán mới.</p><button disabled={save.isPending} onClick={() => save.mutate({row: retiring, values: {is_active: false}})}>Xác nhận ngừng KPI</button><button className="secondary" onClick={() => setRetiring(null)}>Hủy</button></section>}
    {save.isError && <ReviewError error={save.error} reload={() => {void query.refetch().then((result) => {if (editing) setEditing(result.data?.items.find((row) => row.id === editing.id) ?? null); setGeneration((v) => v + 1); save.reset();});}} />}
  </section>
  {hr && <section className="auth-card"><h2>{editing ? "Sửa định nghĩa KPI" : "Thêm định nghĩa KPI"}</h2><DefinitionForm key={`${editing?.id ?? "new"}:${generation}`} initial={editing} pending={save.isPending} onSave={(values) => save.mutate({row: editing, values})} />{editing && <button className="secondary" onClick={() => setEditing(null)}>Hủy chỉnh sửa</button>}</section>}</>;
}
function DefinitionForm({initial, pending, onSave}: {initial: Definition | null; pending: boolean; onSave: (v: Values) => void}) {
  const form = useForm<Values>({resolver: zodResolver(schema), defaultValues: initial ?? {code: "", name: "", unit: "", description: "", direction: "HIGHER_IS_BETTER"}});
  return <form onSubmit={form.handleSubmit(onSave)}>
    <label htmlFor="def-code">Mã KPI</label><input id="def-code" maxLength={32} {...form.register("code")} />
    <label htmlFor="def-name">Tên KPI</label><input id="def-name" maxLength={200} {...form.register("name")} />
    <label htmlFor="def-unit">Đơn vị</label><input id="def-unit" maxLength={50} {...form.register("unit")} />
    <label htmlFor="def-direction">Hướng đánh giá</label><select id="def-direction" {...form.register("direction")}><option value="HIGHER_IS_BETTER">Càng cao càng tốt</option><option value="LOWER_IS_BETTER">Càng thấp càng tốt</option></select>
    <label htmlFor="def-description">Mô tả KPI</label><textarea id="def-description" maxLength={2000} {...form.register("description")} />
    {Object.entries(form.formState.errors).map(([key, error]) => <p key={key} role="alert">{error.message}</p>)}
    <button disabled={pending}>{pending ? "Đang lưu…" : initial ? "Lưu định nghĩa" : "Thêm định nghĩa"}</button>
  </form>;
}
