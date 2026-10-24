"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../auth/auth-provider";
import { organizationApi, referenceLabel, type Reference, type ReferenceInput, type ReferenceKind } from "./api";
import { OrganizationAccess, organizationError, Pagination } from "./shared";

const schema = z.object({
  code: z.string().trim().toUpperCase().regex(/^[A-Z0-9][A-Z0-9_-]{1,31}$/, "Mã gồm 2–32 ký tự: chữ, số, gạch ngang hoặc gạch dưới."),
  label: z.string().trim().min(1, "Nhập tên.").max(200, "Tên tối đa 200 ký tự."),
  is_active: z.boolean(),
});
type Values = z.infer<typeof schema>;
export function ReferenceManagement({ kind }: { kind: ReferenceKind }) {
  return <OrganizationAccess><ReferenceList kind={kind} /></OrganizationAccess>;
}

function ReferenceList({ kind }: { kind: ReferenceKind }) {
  const { user } = useAuth();
  const hr = user?.role === "HR";
  const label = kind === "departments" ? "phòng ban" : "chức danh";
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [active, setActive] = useState("");
  const [editing, setEditing] = useState<Reference | null>(null);
  const [editorVersion, setEditorVersion] = useState(0);
  const [confirm, setConfirm] = useState<{ row: Reference; input: ReferenceInput } | null>(null);
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ["organization", kind, page, q, active], queryFn: () => organizationApi.references(kind, {
    page, page_size: 20, q, is_active: active === "" ? undefined : active === "true",
  }) });
  const mutation = useMutation({ mutationFn: ({ id, input }: { id: string | null; input: ReferenceInput }) => organizationApi.saveReference(kind, id, input),
    onSuccess: () => { setEditing(null); setConfirm(null); setEditorVersion((value) => value + 1); void cache.invalidateQueries({ queryKey: ["organization"] }); },
  });
  function save(values: Values) {
    const input = { code: values.code, [kind === "departments" ? "name" : "title"]: values.label, is_active: values.is_active };
    if (editing?.is_active && !values.is_active) setConfirm({ row: editing, input });
    else mutation.mutate({ id: editing?.id ?? null, input });
  }
  return <>
    <section className="auth-card wide"><p className="eyebrow">TỔ CHỨC</p><h1>Danh sách {label}</h1>
      {!hr && <p>Chỉ hiển thị dữ liệu thuộc phạm vi hồ sơ của bạn.</p>}
      <form className="filters" onSubmit={(event) => {
        event.preventDefault(); const data = new FormData(event.currentTarget);
        setQ(String(data.get("q") ?? "")); setActive(String(data.get("active") ?? "")); setPage(1);
      }}><div><label htmlFor="reference-search">Tìm {label}</label><input id="reference-search" name="q" maxLength={100} /></div>
        <div><label htmlFor="reference-status">Trạng thái</label><select id="reference-status" name="active"><option value="">Tất cả</option><option value="true">Hoạt động</option><option value="false">Ngừng hoạt động</option></select></div>
        <button type="submit">Lọc</button></form>
      {query.isPending && <p role="status">Đang tải…</p>}
      {query.isError && <div role="alert"><p>Không thể tải danh sách.</p><button onClick={() => { void query.refetch(); }}>Thử lại</button></div>}
      {!query.isError && query.data && <>
        {!query.data.items.length && <p>Chưa có {label} phù hợp.</p>}
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Danh mục tổ chức, có thể cuộn ngang"><table><caption>{query.data.total} {label}</caption><thead><tr><th>Mã</th><th>Tên</th><th>Trạng thái</th>{hr && <th>Thao tác</th>}</tr></thead>
          <tbody>{query.data.items.map((row) => <tr key={row.id}><td>{row.code}</td><td>{referenceLabel(row)}</td>
            <td>{row.is_active ? "Hoạt động" : "Ngừng hoạt động"}</td>{hr && <td className="row-actions">
              <button className="secondary" aria-label={`Chỉnh sửa ${row.code}`} disabled={mutation.isPending} onClick={() => setEditing(row)}>Chỉnh sửa</button>
              <button className="secondary" aria-label={`${row.is_active ? "Ngừng hoạt động" : "Kích hoạt"} ${row.code}`} disabled={mutation.isPending} onClick={() => {
                if (row.is_active) setConfirm({ row, input: { is_active: false } });
                else mutation.mutate({ id: row.id, input: { is_active: true } });
              }}>{row.is_active ? "Ngừng hoạt động" : "Kích hoạt"}</button></td>}</tr>)}</tbody></table></div>
        <Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} />
      </>}
      {confirm && <section role="group" aria-label="Xác nhận ngừng hoạt động" className="confirmation">
        <p>Ngừng hoạt động {confirm.row.code}? Hồ sơ hiện hữu được giữ nguyên liên kết; không thể gán mới cho đến khi kích hoạt lại.</p>
        <button disabled={mutation.isPending} onClick={() => mutation.mutate({ id: confirm.row.id, input: confirm.input })}>Xác nhận ngừng hoạt động</button>
        <button className="secondary" onClick={() => setConfirm(null)}>Hủy</button></section>}
      {mutation.isError && <p role="alert">{organizationError(mutation.error)}</p>}
    </section>
    {hr && <section className="auth-card"><h2>{editing ? "Chỉnh sửa" : "Thêm"} {label}</h2>
      <ReferenceEditor key={editing?.id ?? `new-${editorVersion}`} kind={kind} initial={editing} pending={mutation.isPending} onSave={save} />
      {editing && <button className="secondary" onClick={() => setEditing(null)}>Hủy chỉnh sửa</button>}
    </section>}
  </>;
}

function ReferenceEditor({ kind, initial, pending, onSave }: {
  kind: ReferenceKind; initial: Reference | null; pending: boolean; onSave: (value: Values) => void;
}) {
  const label = kind === "departments" ? "phòng ban" : "chức danh";
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: {
    code: initial?.code ?? "", label: initial ? referenceLabel(initial) : "", is_active: initial?.is_active ?? true,
  } });
  return <form onSubmit={form.handleSubmit(onSave)}>
    <label htmlFor="reference-code">Mã {label}</label><input id="reference-code" maxLength={32} {...form.register("code")} />
    <label htmlFor="reference-name">Tên {label}</label><input id="reference-name" maxLength={200} {...form.register("label")} />
    <label className="checkbox-label"><input type="checkbox" {...form.register("is_active")} /> Đang hoạt động</label>
    {Object.entries(form.formState.errors).map(([key, error]) => <p role="alert" key={key}>{error.message}</p>)}
    <button disabled={pending} type="submit">{pending ? "Đang lưu…" : initial ? "Lưu thay đổi" : `Thêm ${label}`}</button>
  </form>;
}
