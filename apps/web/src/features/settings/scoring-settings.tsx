"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../auth/auth-provider";
import { reviewApi, type Policy, type ScoringDefaults } from "../cycles/api";
import { decimalUnits, ReviewError } from "../cycles/shared";

const schema = z.object({kpi_weight: z.string(), feedback_weight: z.string(), kpi_cap: z.string()}).superRefine((v, ctx) => {
  const kpi = decimalUnits(v.kpi_weight, 2, 3), feedback = decimalUnits(v.feedback_weight, 2, 3);
  if (kpi === null || feedback === null || kpi > 10000 || feedback > 10000 || kpi + feedback !== 10000) ctx.addIssue({code: "custom", path: ["kpi_weight"], message: "Hai trọng số phải trong 0–100 và cộng đúng 100.00%."});
  const cap = v.kpi_cap === "" ? null : decimalUnits(v.kpi_cap, 2, 5);
  if (v.kpi_cap !== "" && (cap === null || cap <= 0)) ctx.addIssue({code: "custom", path: ["kpi_cap"], message: "Giới hạn phải là số dương, tối đa 99999.99; để trống nếu không giới hạn."});
});
export function ScoringSettings() {
  const {user} = useAuth();
  return user?.role === "ADMIN" ? <Settings /> : <p role="alert">Chỉ ADMIN được sửa cấu hình mặc định.</p>;
}
function Settings() {
  const cache = useQueryClient();
  const [generation, setGeneration] = useState(0);
  const query = useQuery({queryKey: ["reviews", "defaults"], queryFn: reviewApi.defaults});
  const save = useMutation({mutationFn: ({version, policy}: {version: number; policy: Policy}) => reviewApi.saveDefaults(version, policy), onSuccess: async () => {await cache.invalidateQueries({queryKey: ["reviews"]}); setGeneration((v) => v + 1);}});
  return <section className="auth-card"><h1>Cấu hình chấm điểm mặc định</h1><p>Chỉ áp dụng khi kích hoạt chu kỳ tiếp theo. Chu kỳ đã kích hoạt giữ nguyên cấu hình đã đóng băng.</p>
    {query.isPending && <p role="status">Đang tải cấu hình…</p>}{query.isError && <ReviewError error={query.error} reload={() => {void query.refetch();}} />}
    {query.data && <SettingsForm key={generation} initial={query.data} pending={save.isPending} onSave={(policy, version) => save.mutate({policy, version})} />}
    {save.isSuccess && <p role="status">Đã lưu cấu hình mặc định.</p>}
    {save.isError && <ReviewError error={save.error} reload={() => {void query.refetch().then(() => setGeneration((v) => v + 1));}} />}
  </section>;
}
function SettingsForm({initial, pending, onSave}: {initial: ScoringDefaults; pending: boolean; onSave: (policy: Policy, version: number) => void}) {
  const [version] = useState(initial.version);
  const form = useForm<z.infer<typeof schema>>({resolver: zodResolver(schema), defaultValues: {...initial.policy, kpi_cap: initial.policy.kpi_cap ?? ""}});
  return <form onSubmit={form.handleSubmit((v) => onSave({...v, schema_version: 1, kpi_cap: v.kpi_cap || null}, version))}>
    <label htmlFor="policy-kpi">Trọng số KPI (%)</label><input id="policy-kpi" inputMode="decimal" {...form.register("kpi_weight")} />
    <label htmlFor="policy-feedback">Trọng số phản hồi (%)</label><input id="policy-feedback" inputMode="decimal" {...form.register("feedback_weight")} />
    <label htmlFor="policy-cap">Giới hạn điểm KPI</label><input id="policy-cap" inputMode="decimal" {...form.register("kpi_cap")} /><p>Để trống nếu không giới hạn; khi đó không thể gán KPI càng thấp càng tốt.</p>
    {Object.entries(form.formState.errors).map(([key, error]) => <p key={key} role="alert">{error.message}</p>)}
    <button disabled={pending}>{pending ? "Đang lưu…" : "Lưu cấu hình"}</button>
  </form>;
}
