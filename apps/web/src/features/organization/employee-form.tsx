"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type Ref } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { organizationApi, referenceLabel, type Employee, type EmployeeInput, type ReferenceKind } from "./api";
import { organizationError, Pagination } from "./shared";

const schema = z.object({
  employee_code: z.string().trim().toUpperCase().regex(/^[A-Z0-9][A-Z0-9_-]{1,31}$/, "Mã cần 2–32 ký tự chữ/số/gạch ngang/gạch dưới."),
  display_name: z.string().trim().min(1, "Nhập họ và tên.").max(200, "Tên tối đa 200 ký tự."),
  department_id: z.string().min(1, "Chọn phòng ban."), position_id: z.string().min(1, "Chọn chức danh."),
  manager_id: z.string(), user_id: z.string(), employment_status: z.enum(["ACTIVE", "INACTIVE"]),
});
type Values = z.infer<typeof schema>;

export function EmployeeForm({ initial, onSaved }: { initial?: Employee; onSaved: () => void }) {
  const cache = useQueryClient();
  const [email, setEmail] = useState("");
  const [chosenEmail, setChosenEmail] = useState("");
  const [confirm, setConfirm] = useState<EmployeeInput | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: {
    employee_code: initial?.employee_code ?? "", display_name: initial?.display_name ?? "",
    department_id: initial?.department_id ?? "", position_id: initial?.position_id ?? "",
    manager_id: initial?.manager_id ?? "", user_id: initial?.user_id ?? "", employment_status: initial?.employment_status ?? "ACTIVE",
  } });
  const linkedId = useWatch({ control: form.control, name: "user_id" });
  const lookup = useQuery({ queryKey: ["organization", "account-lookup", email], queryFn: () => organizationApi.lookup(email), enabled: email !== "" });
  const mutation = useMutation({ mutationFn: (input: EmployeeInput) => organizationApi.saveEmployee(initial?.id ?? null, input), onSuccess: () => {
    void cache.invalidateQueries({ queryKey: ["organization"] });
    void cache.invalidateQueries({ queryKey: ["reviews"] });
    void cache.invalidateQueries({ queryKey: ["feedback"] });
    void cache.invalidateQueries({ queryKey: ["performance"] });
    void cache.invalidateQueries({ queryKey: ["ai"] });
    void cache.invalidateQueries({ queryKey: ["users"] });
    void cache.invalidateQueries({ queryKey: ["auth"] }); onSaved();
  } });
  return <section className="auth-card wide" aria-labelledby="employee-editor-title"><h2 id="employee-editor-title">{initial ? "Chỉnh sửa hồ sơ" : "Thêm nhân viên"}</h2>
    <form onSubmit={form.handleSubmit((values) => {
      const input: EmployeeInput = { ...values, manager_id: values.manager_id || null, user_id: values.user_id || null };
      if (initial?.employment_status === "ACTIVE" && values.employment_status === "INACTIVE") setConfirm(input);
      else mutation.mutate(input);
    })}>
      <div className="form-grid">
        <div><label htmlFor="employee-code">Mã nhân viên</label><input id="employee-code" maxLength={32} {...form.register("employee_code")} /></div>
        <div><label htmlFor="employee-name">Họ và tên</label><input id="employee-name" maxLength={200} {...form.register("display_name")} /></div>
        <Controller name="department_id" control={form.control} render={({ field }) => <ReferencePicker kind="departments" value={field.value} onChange={field.onChange} inputRef={field.ref}
          current={initial ? { id: initial.department_id, label: initial.department_name } : undefined} />} />
        <Controller name="position_id" control={form.control} render={({ field }) => <ReferencePicker kind="positions" value={field.value} onChange={field.onChange} inputRef={field.ref}
          current={initial ? { id: initial.position_id, label: initial.position_title } : undefined} />} />
        <Controller name="manager_id" control={form.control} render={({ field }) => <ManagerPicker value={field.value} onChange={field.onChange} self={initial?.id}
          current={initial?.manager_id ? { id: initial.manager_id, label: initial.manager_name ?? "Người quản lý hiện tại" } : undefined} />} />
        <div><label htmlFor="employment-status">Trạng thái làm việc</label><select id="employment-status" {...form.register("employment_status")}><option value="ACTIVE">Đang làm việc</option><option value="INACTIVE">Ngừng làm việc</option></select></div>
      </div>
      <p>{linkedId ? chosenEmail ? `Đã chọn tài khoản: ${chosenEmail}` : "Hồ sơ đã liên kết tài khoản." : "Hồ sơ chưa liên kết tài khoản."}</p>
      {linkedId && <button type="button" className="secondary" onClick={() => { form.setValue("user_id", ""); setChosenEmail(""); }}>Bỏ liên kết tài khoản</button>}
      {Object.entries(form.formState.errors).map(([key, error]) => <p key={key} role="alert">{error.message}</p>)}
      {mutation.isError && <p role="alert">{organizationError(mutation.error)}</p>}
      <button disabled={mutation.isPending} type="submit">{mutation.isPending ? "Đang lưu…" : "Lưu hồ sơ"}</button>
    </form>
    {confirm && <section className="confirmation" role="group" aria-label="Xác nhận ngừng làm việc">
      <p>Chuyển hồ sơ sang ngừng làm việc? Các liên kết hiện hữu vẫn được giữ; trạng thái tài khoản đăng nhập không tự thay đổi.</p>
      <button disabled={mutation.isPending} onClick={() => mutation.mutate(confirm)}>Xác nhận ngừng làm việc</button>
      <button className="secondary" onClick={() => setConfirm(null)}>Hủy</button>
    </section>}
    <hr /><h3>Liên kết tài khoản</h3><p>Tìm đúng email tài khoản đã được ADMIN tạo. Liên kết không thay đổi vai trò hoặc mật khẩu.</p>
    <form onSubmit={(event) => { event.preventDefault(); setEmail(String(new FormData(event.currentTarget).get("email") ?? "").trim()); }}>
      <label htmlFor="linked-email">Email tài khoản cần liên kết</label><input id="linked-email" name="email" type="email" required maxLength={254} />
      <button type="submit" disabled={lookup.isFetching}>Tìm tài khoản</button>
    </form>
    {lookup.isError && <p role="alert">Không thể tra cứu tài khoản. Hãy thử lại.</p>}
    {!lookup.isError && lookup.data && !lookup.data.items.length && <p>Không tìm thấy tài khoản với email này.</p>}
    {lookup.data?.items.map((account) => <div className="confirmation" key={account.id}>
      <p>{account.email}</p><p>{account.is_active ? "Tài khoản hoạt động" : "Tài khoản đã bị vô hiệu hóa"}</p>
      {account.employee_id && account.employee_id !== initial?.id
        ? <p role="alert">Tài khoản đã liên kết hồ sơ khác.</p>
        : <button type="button" onClick={() => { form.setValue("user_id", account.id); setChosenEmail(account.email); }}>Liên kết tài khoản này</button>}
    </div>)}
  </section>;
}

export function ReferencePicker({ kind, value, onChange, current, inputRef, labelOverride, activeOnly = true }: {
  kind: ReferenceKind; value: string; onChange: (value: string) => void;
  current?: { id: string; label: string }; inputRef?: Ref<HTMLSelectElement>;
  labelOverride?: string; activeOnly?: boolean;
}) {
  const [q, setQ] = useState(""); const [page, setPage] = useState(1);
  const id = useId();
  const [selected, setSelected] = useState(current);
  const label = kind === "departments" ? "Phòng ban" : "Chức danh";
  const query = useQuery({ queryKey: ["organization", "options", kind, q, page, activeOnly], queryFn: () => organizationApi.references(kind, { q, page, page_size: 20, is_active: activeOnly ? true : undefined }) });
  return <div><label htmlFor={`${id}-search`}>Tìm {label.toLowerCase()}</label><input id={`${id}-search`} value={q} onChange={(event) => { setQ(event.target.value); setPage(1); }} maxLength={100} />
    <label htmlFor={`${id}-select`}>{labelOverride ?? label}</label><select id={`${id}-select`} ref={inputRef} value={value} onChange={(event) => {
      const row = query.data?.items.find((item) => item.id === event.target.value);
      setSelected(row ? { id: row.id, label: referenceLabel(row) } : undefined);
      onChange(event.target.value);
    }}>
      <option value="">Chọn {label.toLowerCase()}</option>
      {selected && !query.data?.items.some((row) => row.id === selected.id) && <option value={selected.id}>{selected.label} (đã chọn)</option>}
      {query.data?.items.map((row) => <option key={row.id} value={row.id}>{referenceLabel(row)} ({row.code})</option>)}
    </select>{query.isError && <p role="alert">Không thể tải {label.toLowerCase()}.</p>}
    {!query.isError && query.data && query.data.total > 20 && <Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} />}
  </div>;
}

function ManagerPicker({ value, onChange, self, current }: {
  value: string; onChange: (value: string) => void; self?: string; current?: { id: string; label: string };
}) {
  const [q, setQ] = useState(""); const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(current);
  const query = useQuery({ queryKey: ["organization", "manager-options", q, page], queryFn: () => organizationApi.employees({ q, page, page_size: 20, employment_status: "ACTIVE" }) });
  return <div><label htmlFor="manager-search">Tìm người quản lý</label><input id="manager-search" value={q} maxLength={100} onChange={(event) => { setQ(event.target.value); setPage(1); }} />
    <label htmlFor="manager-select">Người quản lý</label><select id="manager-select" value={value} onChange={(event) => {
      const row = query.data?.items.find((item) => item.id === event.target.value);
      setSelected(row ? { id: row.id, label: row.display_name } : undefined);
      onChange(event.target.value);
    }}>
      <option value="">Không có</option>{selected && !query.data?.items.some((row) => row.id === selected.id) && <option value={selected.id}>{selected.label} (đã chọn)</option>}
      {query.data?.items.filter((row) => row.id !== self).map((row) => <option key={row.id} value={row.id}>{row.display_name} ({row.employee_code})</option>)}
    </select>{query.isError && <p role="alert">Không thể tải danh sách người quản lý.</p>}
    {!query.isError && query.data && query.data.total > 20 && <Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} />}
  </div>;
}
