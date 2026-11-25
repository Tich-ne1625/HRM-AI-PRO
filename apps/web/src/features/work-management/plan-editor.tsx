"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Pagination } from "../organization/shared";
import { workApi, type Goal, type Plan } from "./api";
import { useWorkCommand, WorkError, type DraftDirty } from "./workspace";

type Line = Omit<Goal, "id" | "definition"> & {key: string; name: string; milestoneText: string};
const blank = (): Line => ({key: crypto.randomUUID(), name: "", definition_id: "", baseline: "0", target: "", weight: "", method: "SUM", source: "", acceptance: "", numerator: "", denominator: "", milestones: [], milestoneText: ""});
export function PlanEditor({initial, participant, dirty, done}: {initial?: Plan; participant: string; dirty: DraftDirty; done: () => void}) {
  const [version] = useState(initial?.version ?? 1);
  const [objective, setObjective] = useState(initial?.objective ?? "");
  const [lines, setLines] = useState<Line[]>(() => initial?.goals.map((g) => ({...g, key: g.id, name: g.definition.name, milestoneText: g.milestones.map((m) => `${m.title} | ${m.weight}`).join("\n")})) ?? [blank()]);
  const [page, setPage] = useState(1), [q, setQ] = useState("");
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null), [error, setError] = useState("");
  const definitions = useQuery({queryKey: ["work-management", "definitions", page, q], queryFn: () => workApi.definitions(page, q)});
  const mutation = useWorkCommand(() => {dirty(false, "plan-editor"); done();});
  const change = (key: string, values: Partial<Line>) => {setLines((old) => old.map((line) => line.key === key ? {...line, ...values} : line)); dirty(true, "plan-editor"); setPreview(null);};
  const total = lines.reduce((sum, line) => sum + Number(line.weight || 0), 0);
  return <form className="work-form" onSubmit={(e) => {
    e.preventDefault(); setError("");
    if (Math.abs(total - 100) > 0.00001) {setError("Tổng trọng số các mục tiêu phải bằng 100%."); return;}
    try {
      const goals = lines.map((line) => {
        const milestones = line.method === "MILESTONE" ? line.milestoneText.split("\n").filter((s) => s.trim()).map((s) => {const [title, weight, extra] = s.split("|").map((p) => p.trim()); if (!title || !weight || extra || !(Number(weight) > 0)) throw new Error("Mỗi mốc nhập: tên mốc | trọng số."); return {title, weight};}) : [];
        if (!line.definition_id) throw new Error("Chọn KPI cho từng mục tiêu.");
        if (line.method === "MILESTONE" && Math.abs(milestones.reduce((n, m) => n + Number(m.weight), 0) - 100) > 0.00001) throw new Error("Các mốc của một mục tiêu phải có tổng 100%.");
        return {definition_id: line.definition_id, baseline: line.baseline, target: line.target, weight: line.weight, method: line.method, source: line.source, acceptance: line.acceptance, numerator: line.method === "RATIO" ? line.numerator : null, denominator: line.method === "RATIO" ? line.denominator : null, milestones};
      });
      setPreview({expected_version: version, objective, goals});
    } catch (err) {setError(err instanceof Error ? err.message : "Kiểm tra cách nhập mục tiêu.");}
  }}>
    <h3>{initial ? "Sửa kế hoạch · lưu thành bản mới" : "Soạn kế hoạch cá nhân"}</h3><label>Mục tiêu chung<textarea rows={3} required maxLength={6000} value={objective} onChange={(e) => {setObjective(e.target.value); dirty(true, "plan-editor"); setPreview(null);}} /></label>
    <div className="work-definition-search"><label>Tìm danh mục KPI<input value={q} maxLength={100} onChange={(e) => {setQ(e.target.value); setPage(1);}} placeholder="Mã hoặc tên KPI" /></label>{definitions.isError && <WorkError error={definitions.error} />}{definitions.data && <Pagination page={page} total={definitions.data.total} pending={definitions.isFetching} onPage={setPage} />}<small>Chọn KPI từ trang danh mục hiện tại; các lựa chọn đã chọn được giữ khi tìm kiếm.</small></div>
    {lines.map((line, index) => <fieldset className="work-goal-editor" key={line.key}><legend>Mục tiêu {index + 1}</legend>
      <label>KPI<select required value={line.definition_id} onChange={(e) => change(line.key, {definition_id: e.target.value, name: definitions.data?.items.find((d) => d.id === e.target.value)?.name ?? ""})}><option value="">Chọn KPI</option>{line.definition_id && !definitions.data?.items.some((d) => d.id === line.definition_id) && <option value={line.definition_id}>{line.name}</option>}{definitions.data?.items.map((d) => <option key={d.id} value={d.id}>{d.code} · {d.name}</option>)}</select></label>
      <div className="work-numbers"><label>Giá trị ban đầu<input type="number" required min="0" step="0.0001" value={line.baseline} onChange={(e) => change(line.key, {baseline: e.target.value})} /></label><label>Mục tiêu cần đạt<input type="number" required min="0.0001" step="0.0001" value={line.target} onChange={(e) => change(line.key, {target: e.target.value})} /></label><label>Trọng số (%)<input type="number" required min="0.01" max="100" step="0.01" value={line.weight} onChange={(e) => change(line.key, {weight: e.target.value})} /></label></div>
      <label>Cách tổng hợp<select value={line.method} onChange={(e) => change(line.key, {method: e.target.value as Line["method"]})}><option value="SUM">Cộng phát sinh đã xác minh</option><option value="LAST">Giá trị chốt gần nhất</option><option value="RATIO">Tổng tử / tổng mẫu</option><option value="MILESTONE">Các mốc có tỷ trọng</option></select></label>
      {line.method === "RATIO" && <div className="form-grid"><label>Định nghĩa tử số<input required maxLength={200} value={line.numerator ?? ""} onChange={(e) => change(line.key, {numerator: e.target.value})} /></label><label>Định nghĩa mẫu số<input required maxLength={200} value={line.denominator ?? ""} onChange={(e) => change(line.key, {denominator: e.target.value})} /></label></div>}
      {line.method === "MILESTONE" && <label>Mốc và trọng số (mỗi dòng: tên mốc | tỷ trọng)<textarea required value={line.milestoneText} onChange={(e) => change(line.key, {milestoneText: e.target.value})} placeholder={"Hoàn thành bản nháp | 40\nNghiệm thu | 60"} /></label>}
      <label>Nguồn số liệu / mã hồ sơ đối chiếu<textarea required rows={2} maxLength={6000} value={line.source} onChange={(e) => change(line.key, {source: e.target.value})} /></label><label>Tiêu chuẩn nghiệm thu<textarea required rows={2} maxLength={6000} value={line.acceptance} onChange={(e) => change(line.key, {acceptance: e.target.value})} /></label>
      {lines.length > 1 && <button className="secondary" type="button" onClick={() => {setLines(lines.filter((l) => l.key !== line.key)); dirty(true, "plan-editor"); setPreview(null);}}>Bỏ mục tiêu {index + 1}</button>}
    </fieldset>)}
    <div className="row-actions"><button type="button" className="secondary" disabled={lines.length >= 30} onClick={() => {setLines([...lines, blank()]); dirty(true, "plan-editor"); setPreview(null);}}>Thêm mục tiêu</button><strong>Tổng trọng số: {Number(total.toFixed(2))}% / 100%</strong></div>
    {error && <p role="alert">{error}</p>}
    {preview ? <div className="confirmation"><h4>Xem lại kế hoạch</h4><p>{objective}</p><ul>{lines.map((line) => <li key={line.key}>{line.name}: {line.baseline} → {line.target} · {line.weight}%</li>)}</ul><p>Lưu bản nháp chưa đồng nghĩa đã duyệt. Sau đó gửi, duyệt và yêu cầu nhân viên xác nhận.</p><button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate({path: `participants/${participant}/plan`, body: preview})}>Lưu bản kế hoạch</button><button type="button" className="secondary" onClick={() => setPreview(null)}>Tiếp tục chỉnh sửa</button></div> : <button disabled={mutation.isPending}>Xem lại kế hoạch</button>}
    {mutation.isError && <WorkError error={mutation.error} />}
  </form>;
}
