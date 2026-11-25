"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState, type ReactNode } from "react";
import { ApiClientError } from "../../lib/api-client";
import { useAuth } from "../auth/auth-provider";
import { Pagination } from "../organization/shared";
import { WorkspaceDialog } from "../workspace/dialog";
import { actionLabel, statusLabel, workApi, type Plan, type Work, type WorkParticipant } from "./api";
import { PlanEditor } from "./plan-editor";

const tabs = ["Nội dung", "Tiến trình & bằng chứng", "Trao đổi", "Lịch sử"];
const date = (value: string) => new Date(value).toLocaleString("vi-VN");
export type DraftDirty = (value: boolean, source?: string) => void;

export function WorkError({error, reload}: {error: Error | null; reload?: () => void}) {
  const messages: Record<string, string> = {
    stale_version: "Dữ liệu vừa thay đổi. Bản nhập của bạn vẫn được giữ; tải lại phiên bản trước khi gửi.",
    work_state_conflict: "Bước này không còn khả dụng. Hãy kiểm tra trạng thái mới.",
    plan_state_conflict: "Kế hoạch đã chuyển bước. Hãy kiểm tra phiên bản mới.",
    validation_error: "Kiểm tra các trường bắt buộc, tổng trọng số 100% và định nghĩa cách đo.",
    work_not_found: "Không tìm thấy nội dung trong phạm vi của bạn.",
    baseline_frozen: "Kế hoạch đã đóng băng khi kỳ bắt đầu. Hãy gửi đề nghị thay đổi.",
    invalid_work_deadline: "Hạn công việc phải ở tương lai và trong khoảng ngày của kỳ.",
    duplicate_work_source: "Mã nguồn này đã có công việc. Chọn mã hồ sơ khác.",
    workflow_cutoff: "Đã qua hạn thực hiện bước này. Liên hệ HR để xử lý theo quy trình.",
    forbidden: "Bạn không còn quyền thực hiện bước này.",
    work_not_ready: "Kế hoạch cần được duyệt, xác nhận và kích hoạt trước khi giao việc.",
  };
  return <div role="alert" className="work-error">{error instanceof ApiClientError ? messages[error.code] ?? "Chưa lưu được. Kiểm tra dữ liệu hoặc thử lại." : "Chưa kết nối được máy chủ. Bản nhập vẫn được giữ."}{reload && <button type="button" onClick={reload}>Tải lại trạng thái</button>}</div>;
}

export function useWorkCommand<T = unknown>(onSuccess: (data: T) => void) {
  const cache = useQueryClient();
  const previous = useRef<{body: string; id: string} | null>(null);
  return useMutation({mutationFn: ({path, body}: {path: string; body: Record<string, unknown>}) => {
    const signature = JSON.stringify({path, body});
    if (previous.current?.body !== signature) previous.current = {body: signature, id: crypto.randomUUID()};
    return workApi.write<T>(path, {...body, client_request_id: previous.current.id});
  }, onSuccess: async (data) => {
    previous.current = null;
    onSuccess(data);
    await Promise.all(["work-management", "notifications", "reviews"].map((domain) => cache.invalidateQueries({queryKey: [domain]})));
  }});
}

type Selection = {kind: "plan" | "item"; id: string} | {kind: "draft"; participant: WorkParticipant} | null;
export function WorkWorkspace() {
  const {user} = useAuth();
  if (!user || user.role === "ADMIN") return <p role="alert">Bạn không có quyền truy cập công việc.</p>;
  return <Workspace key={`${user.id}:${user.role}`} hr={user.role === "HR"} manager={user.role === "MANAGER"} />;
}
function Workspace({hr, manager}: {hr: boolean; manager: boolean}) {
  const search = useSearchParams();
  const router = useRouter();
  const [selection, setSelection] = useState<Selection | undefined>(undefined);
  const [view, setView] = useState(hr ? "plans" : "items");
  const [page, setPage] = useState(1), [planPage, setPlanPage] = useState(1);
  const [status, setStatus] = useState(""), [blocked, setBlocked] = useState("");
  const cycle = search.get("cycle_id") ?? undefined;
  const selected = selection === undefined ? search.get("item") ? {kind: "item" as const, id: search.get("item")!} : search.get("plan") ? {kind: "plan" as const, id: search.get("plan")!} : null : selection;
  const close = () => { setSelection(null); if (search.has("item") || search.has("plan")) router.replace(`/work-management${cycle ? `?cycle_id=${cycle}` : ""}`, {scroll: false}); };
  const plans = useQuery({queryKey: ["work-management", "participants", planPage, cycle], queryFn: () => workApi.participants(planPage, cycle)});
  const work = useQuery({queryKey: ["work-management", "items", page, status, blocked], queryFn: () => workApi.items(page, status, blocked), enabled: !hr && view === "items"});
  return <div className="work-area">
    <section className="auth-card wide"><p className="eyebrow">CÔNG VIỆC & MỤC TIÊU</p><h1>{hr ? "Theo dõi kế hoạch" : manager ? "Điều phối nhóm" : "Công việc của tôi"}</h1>
      <p>{hr ? "Theo dõi hai bên thống nhất kế hoạch trước khi kích hoạt chu kỳ. Quản lý chịu trách nhiệm tiêu chuẩn và nghiệm thu." : manager ? "Thống nhất mục tiêu, giao đầu ra rõ ràng và duyệt bằng chứng của nhân viên trực tiếp." : "Xác nhận mục tiêu, cập nhật công việc và gửi bằng chứng cho quản lý."}</p>
      <div className="work-tabs" role="group" aria-label="Loại nội dung công việc">{!hr && <button aria-pressed={view === "items"} onClick={() => setView("items")}>Công việc</button>}<button aria-pressed={view === "plans"} onClick={() => setView("plans")}>Kế hoạch & mục tiêu</button></div>
    </section>
    {view === "plans" ? <section className="auth-card wide"><h2>Kế hoạch cá nhân</h2>
      {plans.isPending && <p role="status">Đang tải kế hoạch…</p>}{plans.isError && <WorkError error={plans.error} reload={() => {void plans.refetch();}} />}
      {plans.data && <><div className="work-cards">{plans.data.items.map((p) => <article className="work-card" key={p.participant_id}><small>{p.cycle_name} · {p.cycle_status === "DRAFT" ? "Chuẩn bị" : "Đang thực hiện"}</small><h3>{p.employee_name}</h3><span className="work-badge">{p.plan_status ? statusLabel[p.plan_status] : "Chưa có kế hoạch"}</span><p>{p.acknowledged ? "Nhân viên đã xác nhận bản hiện hành" : "Chưa xác nhận bản hiện hành"}</p>{p.needs_hr && <p role="status">Cần HR kiểm tra tài khoản / quản lý.</p>}<div className="row-actions">{p.plan_id && <button onClick={() => setSelection({kind: "plan", id: p.plan_id!})}>Xem kế hoạch</button>}{!p.plan_id && p.can_draft && <button onClick={() => setSelection({kind: "draft", participant: p})}>Lập kế hoạch</button>}</div></article>)}</div>
        {!plans.data.total && <div className="work-empty"><h3>Chưa có kỳ quản lý công việc</h3><p>HR tạo chu kỳ theo tiến trình và thêm người tham gia. Các kỳ đánh giá cũ vẫn ở mục Chu kỳ đánh giá.</p></div>}<Pagination page={planPage} total={plans.data.total} pending={plans.isFetching} onPage={setPlanPage} /></>}
    </section> : <section className="auth-card wide"><div className="section-heading"><h2>{manager ? "Công việc trong nhóm" : "Việc cần theo dõi"}</h2></div>
      <div className="filters"><div><label htmlFor="work-status">Trạng thái</label><select id="work-status" value={status} onChange={(e) => {setStatus(e.target.value); setPage(1);}}><option value="">Tất cả</option>{["PROPOSED", "TODO", "IN_PROGRESS", "SUBMITTED", "CHANGES_REQUESTED", "ACCEPTED", "CANCELLED"].map((s) => <option value={s} key={s}>{s === "SUBMITTED" ? "Chờ nghiệm thu" : statusLabel[s]}</option>)}</select></div><label className="checkbox-label"><input type="checkbox" checked={blocked === "true"} onChange={(e) => {setBlocked(e.target.checked ? "true" : ""); setPage(1);}} />Chỉ việc bị vướng</label></div>
      {work.isPending && <p role="status">Đang tải công việc…</p>}{work.isError && <WorkError error={work.error} reload={() => {void work.refetch();}} />}
      {work.data && <><div className="work-cards">{work.data.items.map((w) => <article className={`work-card ${w.blocked ? "work-blocked" : ""}`} key={w.id}><small>{w.employee_name} · {w.priority === "HIGH" ? "Ưu tiên cao" : w.priority === "LOW" ? "Ưu tiên thấp" : "Bình thường"}</small><h3>{w.title}</h3><span className="work-badge">{w.status === "SUBMITTED" ? "Chờ nghiệm thu" : statusLabel[w.status]}</span>{w.blocked && <p className="work-warning">Đang vướng: {w.blocked_reason}</p>}<p>Hạn: {date(w.due_at)}<br />Bước tiếp theo: {w.next_actor}</p><button onClick={() => setSelection({kind: "item", id: w.id})}>Mở công việc</button></article>)}</div>
        {!work.data.total && <div className="work-empty"><h3>Chưa có công việc phù hợp</h3><p>Mở Kế hoạch & mục tiêu để xem mục tiêu và giao việc khi chu kỳ đã bắt đầu.</p></div>}<Pagination page={page} total={work.data.total} pending={work.isFetching} onPage={setPage} /></>}
    </section>}
    {selected?.kind === "draft" && <WorkModal title={`Lập kế hoạch · ${selected.participant.employee_name}`} close={close}>{(dirty) => <PlanEditor participant={selected.participant.participant_id} dirty={dirty} done={close} />}</WorkModal>}
    {selected?.kind === "plan" && <PlanDialog key={selected.id} id={selected.id} close={close} />}
    {selected?.kind === "item" && <ItemDialog key={selected.id} id={selected.id} close={close} />}
  </div>;
}

function WorkModal({title, close, children}: {title: string; close: () => void; children: (dirty: DraftDirty) => ReactNode}) {
  const [drafts, setDrafts] = useState(() => new Set<string>()), [confirm, setConfirm] = useState(false);
  const dirty = drafts.size > 0;
  const markDirty: DraftDirty = (value, source = "default") => setDrafts((previous) => {const next = new Set(previous); if (value) next.add(source); else next.delete(source); return next;});
  return <WorkspaceDialog title={title} variant="content" close={() => dirty ? setConfirm(true) : close()}>
    <div className="work-area">{confirm && <div role="alert" className="confirmation"><p>Bạn có nội dung chưa lưu. Đóng sẽ bỏ bản nhập này.</p><button onClick={close}>Bỏ bản nhập và đóng</button><button className="secondary" onClick={() => setConfirm(false)}>Tiếp tục chỉnh sửa</button></div>}{children(markDirty)}</div>
  </WorkspaceDialog>;
}

function DetailTabs({active, change}: {active: number; change: (n: number) => void}) {
  return <div className="work-tabs" role="tablist" aria-label="Chi tiết công việc" onKeyDown={(e) => {
    const next = e.key === "ArrowRight" ? (active + 1) % tabs.length : e.key === "ArrowLeft" ? (active + tabs.length - 1) % tabs.length : e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : null;
    if (next !== null) {e.preventDefault(); change(next); e.currentTarget.querySelectorAll<HTMLButtonElement>("button")[next]?.focus();}
  }}>{tabs.map((t, i) => <button role="tab" tabIndex={active === i ? 0 : -1} aria-selected={active === i} aria-controls={`work-panel-${i}`} id={`work-tab-${i}`} key={t} onClick={() => change(i)}>{t}</button>)}</div>;
}
function Panel({index, active, children}: {index: number; active: number; children: ReactNode}) {
  return <section role="tabpanel" id={`work-panel-${index}`} aria-labelledby={`work-tab-${index}`} hidden={index !== active}>{children}</section>;
}

function PlanDialog({id, close}: {id: string; close: () => void}) {
  const query = useQuery({queryKey: ["work-management", "plan", id], queryFn: () => workApi.plan(id)});
  return <WorkModal title="Kế hoạch cá nhân" close={close}>{(dirty) => query.isPending ? <p role="status">Đang tải kế hoạch…</p> : query.isError ? <WorkError error={query.error} /> : <PlanContent plan={query.data} dirty={dirty} />}</WorkModal>;
}
function PlanContent({plan, dirty}: {plan: Plan; dirty: DraftDirty}) {
  const [active, setActive] = useState(0), [editing, setEditing] = useState(false), [creating, setCreating] = useState(false);
  return <><p className="eyebrow">{plan.employee_name} · Bản {plan.revision} · {statusLabel[plan.status]}</p><h3>{plan.cycle_name}</h3><DetailTabs active={active} change={setActive} />
    <Panel index={0} active={active}><p className="work-prose">{plan.objective}</p><p>{plan.acknowledged_revision === plan.revision ? "Đã xác nhận đúng phiên bản" : "Chưa xác nhận phiên bản này"} · {plan.start_date} → {plan.end_date}</p>
      <div className="work-goals">{plan.goals.map((goal) => <article className="work-card" key={goal.id}><h4>{goal.definition.name} · {goal.weight}%</h4><p>Ban đầu: {goal.baseline} → Mục tiêu: {goal.target} {goal.definition.unit}</p><dl><dt>Cách tổng hợp</dt><dd>{{SUM: "Tổng số phát sinh", LAST: "Giá trị chốt gần nhất", RATIO: "Tỷ lệ từ tổng tử / tổng mẫu", MILESTONE: "Mốc hoàn thành"}[goal.method]}</dd><dt>Nguồn đo</dt><dd>{goal.source}</dd><dt>Chuẩn nghiệm thu</dt><dd>{goal.acceptance}</dd></dl>{goal.method === "RATIO" && <p>Tử: {goal.numerator}<br />Mẫu: {goal.denominator}</p>}{goal.milestones.map((m) => <p key={m.title}>{m.title}: {m.weight}%</p>)}</article>)}</div>
      {plan.actions.includes("edit") && !editing && <button className="secondary" onClick={() => setEditing(true)}>Chỉnh sửa kế hoạch</button>}
      <div hidden={!editing}>{editing && <PlanEditor initial={plan} participant={plan.participant_id} dirty={dirty} done={() => {dirty(false); setEditing(false);}} />}</div>
      {!editing && <ActionForm kind="plan" plan={plan} dirty={dirty} />}
    </Panel>
    <Panel index={1} active={active}><h3>Công việc gắn với kế hoạch</h3><p>Đầu ra được quản lý nghiệm thu. Dữ liệu công việc chưa tạo actual hoặc điểm KPI ở bước này.</p>{plan.can_create_work && <>{!creating && <button onClick={() => setCreating(true)}>{plan.is_manager ? "Giao công việc" : "Đề xuất công việc"}</button>}<div hidden={!creating}>{creating && <WorkForm plan={plan} dirty={dirty} done={() => {dirty(false); setCreating(false);}} />}</div></>}{!plan.can_create_work && <p>Chờ kỳ được kích hoạt và kế hoạch được xác nhận.</p>}</Panel>
    <Panel index={2} active={active}><h3>Trao đổi về mục tiêu</h3><ActionForm kind="plan" plan={plan} dirty={dirty} discussion /><History plan={plan.id} discussion /></Panel>
    <Panel index={3} active={active}><RevisionHistory plan={plan.id} /><History plan={plan.id} /></Panel>
  </>;
}

function ItemDialog({id, close}: {id: string; close: () => void}) {
  const [page, setPage] = useState(1);
  const query = useQuery({queryKey: ["work-management", "item", id, page], queryFn: () => workApi.item(id, page)});
  return <WorkModal title="Chi tiết công việc" close={close}>{(dirty) => query.isPending ? <p role="status">Đang tải công việc…</p> : query.isError ? <WorkError error={query.error} /> : <ItemContent work={query.data} dirty={dirty} page={page} setPage={setPage} />}</WorkModal>;
}
function ItemContent({work, dirty, page, setPage}: {work: Work; dirty: DraftDirty; page: number; setPage: (n: number) => void}) {
  const [active, setActive] = useState(0);
  const [editing, setEditing] = useState(false);
  const plan = useQuery({queryKey: ["work-management", "plan", work.plan_id], queryFn: () => workApi.plan(work.plan_id), enabled: editing && work.actions.includes("edit_proposal")});
  return <><p className="eyebrow">{work.employee_name} · {work.status === "SUBMITTED" ? "Chờ nghiệm thu" : statusLabel[work.status]}</p><h3>{work.title}</h3><p>Đang giữ bước: {work.next_actor}</p>{work.needs_hr && <p className="work-warning">Tài khoản quản lý cần HR kiểm tra. Quyền duyệt không tự chuyển cho người khác.</p>}<DetailTabs active={active} change={setActive} />
    <Panel index={0} active={active}><h4>Đầu ra được cam kết</h4><p className="work-prose">{work.acceptance}</p><p>Hạn: {date(work.due_at)}<br />Nguồn hồ sơ: {work.source_key}<br />{work.goal_id ? "Có gắn mục tiêu KPI" : "Công việc hỗ trợ · không đo KPI"}</p>{work.blocked && <p className="work-warning">Đang vướng: {work.blocked_reason}</p>}<p className="help-text">Muốn đổi hạn hoặc tiêu chuẩn sau khi giao? Gửi đề nghị trong tab Trao đổi; các thông tin đã cam kết được giữ nguyên.</p>{work.actions.some((a) => !["edit_proposal", "comment", "request_change"].includes(a)) && <button onClick={() => setActive(1)}>Thực hiện / cập nhật tiến trình</button>}{work.actions.includes("edit_proposal") && !editing && <button onClick={() => setEditing(true)}>Chỉnh sửa đề xuất</button>}{editing && <>{plan.isPending && <p>Đang tải mục tiêu…</p>}{plan.isError && <WorkError error={plan.error} />}{plan.data && <WorkForm plan={plan.data} initial={work} dirty={dirty} done={() => setEditing(false)} />}</>}</Panel>
    <Panel index={1} active={active}><h3>Tiến trình & bằng chứng</h3><ActionForm kind="work" work={work} dirty={dirty} />{work.submissions?.map((s) => <article className="work-card" key={s.id}><h4>Lần nộp {s.number}</h4><small>{date(s.created_at)}</small><p className="work-prose">{s.body}</p>{s.url && <a href={s.url} rel="noreferrer noopener" target="_blank">Mở liên kết bằng chứng ↗</a>}</article>)}{!work.submissions?.length && <p>Chưa có bản nộp. Cập nhật tiến trình và nộp khi đã sẵn sàng.</p>}<Pagination page={page} total={work.submission_total ?? 0} pending={false} onPage={setPage} /></Panel>
    <Panel index={2} active={active}><p>Trao đổi này được chia sẻ giữa người thực hiện và quản lý. Đề nghị thay đổi được ghi lại, chưa tự sửa cam kết.</p><ActionForm kind="work" work={work} dirty={dirty} discussion /><History plan={work.plan_id} work={work.id} discussion /></Panel>
    <Panel index={3} active={active}><History plan={work.plan_id} work={work.id} /></Panel>
  </>;
}

function ActionForm({kind, work, plan, dirty, discussion = false}: {kind: "plan" | "work"; work?: Work; plan?: Plan; dirty: DraftDirty; discussion?: boolean}) {
  const entity = work ?? plan!;
  const [version, setVersion] = useState(entity.version);
  const order = ["acknowledge", "approve", "publish", "start", "submit", "accept", "return", "update", "block", "unblock", "clarify", "cancel", "reopen", "comment", "request_change"];
  const choices = entity.actions.filter((a) => !["edit", "edit_proposal"].includes(a) && (discussion ? ["comment", "request_change"].includes(a) : !["comment", "request_change"].includes(a))).sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const [choice, setChoice] = useState(""), [body, setBody] = useState(""), [url, setUrl] = useState(""), [confirm, setConfirm] = useState(false);
  const action = choices.includes(choice) ? choice : choices[0] ?? "";
  const mutation = useWorkCommand<{version: number}>((data) => {dirty(false, `action:${kind}:${discussion}`); setBody(""); setUrl(""); setConfirm(false); setVersion(data.version);});
  if (!choices.length) return <p className="help-text">{discussion ? "Không có quyền trao đổi tại bước này." : "Không có thao tác đang chờ bạn ở bước này."}</p>;
  const requiresText = ["update", "block", "submit", "return", "accept", "cancel", "reopen", "comment", "request_change", "clarify"].includes(action) && !(kind === "plan" && action === "submit");
  const send = () => mutation.mutate({path: `${kind === "plan" ? "plans" : "items"}/${entity.id}/actions`, body: {
    action, expected_version: version, ...(kind === "plan" ? {revision: plan!.revision} : {}),
    ...(body.trim() ? {body} : {}), ...(kind === "work" && action === "submit" && url ? {url} : {}),
  }});
  return <form className="work-form" onSubmit={(e) => {e.preventDefault(); setConfirm(true);}}>
    <label>Thao tác<select disabled={mutation.isPending} value={action} onChange={(e) => {setChoice(e.target.value); setConfirm(false);}}>{choices.map((a) => <option key={a} value={a}>{kind === "work" && a === "submit" ? "Nộp bằng chứng" : actionLabel[a]}</option>)}</select></label>
    {requiresText && <label>{action === "submit" ? "Bằng chứng và kết quả thực hiện" : "Nội dung / lý do"}<textarea disabled={mutation.isPending} required maxLength={6000} rows={4} value={body} onChange={(e) => {setBody(e.target.value); dirty(true, `action:${kind}:${discussion}`); setConfirm(false);}} /></label>}
    {kind === "work" && action === "submit" && <label>Liên kết bằng chứng (không bắt buộc)<input disabled={mutation.isPending} type="url" value={url} onChange={(e) => {setUrl(e.target.value); dirty(true, `action:${kind}:${discussion}`); setConfirm(false);}} placeholder="https://…" /></label>}
    {entity.version > version && <p role="status">Có cập nhật mới. Nội dung nhập vẫn được giữ. <button type="button" onClick={() => {setVersion(entity.version); setConfirm(false);}}>Dùng phiên bản mới sau khi xem lại</button></p>}
    {confirm ? <div className="confirmation"><p>Xác nhận: {kind === "work" && action === "submit" ? "Nộp bằng chứng cho quản lý. Bản nộp sẽ được giữ trong lịch sử." : actionLabel[action]}{kind === "plan" ? ` · kế hoạch bản ${plan!.revision}` : ` · ${work!.title}`}.</p><button type="button" disabled={mutation.isPending || entity.version > version} onClick={send}>Xác nhận gửi</button><button type="button" className="secondary" onClick={() => setConfirm(false)}>Xem lại</button></div> : <button disabled={mutation.isPending || entity.version > version}>Xem lại trước khi gửi</button>}
    {mutation.isError && <WorkError error={mutation.error} />}{mutation.isSuccess && <p role="status">Đã lưu thay đổi.</p>}
  </form>;
}

function WorkForm({plan, initial, dirty, done}: {plan: Plan; initial?: Work; dirty: DraftDirty; done: () => void}) {
  const [confirm, setConfirm] = useState<Record<string, unknown> | null>(null);
  const mutation = useWorkCommand(() => {dirty(false, "new-work"); done();});
  const [version] = useState(initial?.version ?? plan.version);
  const localDue = initial ? new Date(new Date(initial.due_at).getTime() - new Date(initial.due_at).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "";
  return <form className="work-form" onChange={() => {dirty(true, "new-work"); setConfirm(null);}} onSubmit={(e) => {e.preventDefault(); const f = new FormData(e.currentTarget); setConfirm({expected_version: version, title: f.get("title"), acceptance: f.get("acceptance"), source_key: f.get("source"), goal_id: f.get("goal") || null, priority: f.get("priority"), due_at: new Date(String(f.get("due"))).toISOString()});}}>
    <label>Tên công việc<input name="title" required maxLength={200} defaultValue={initial?.title} /></label><label>Đầu ra và tiêu chuẩn nghiệm thu<textarea name="acceptance" rows={3} required maxLength={6000} defaultValue={initial?.acceptance} /></label>
    <div className="form-grid"><label>Mã nguồn / hồ sơ duy nhất<input name="source" required maxLength={120} defaultValue={initial?.source_key} placeholder="VD: CSKH-2026-001" /></label><label>Hạn hoàn thành<input name="due" type="datetime-local" required min={`${plan.start_date}T00:00`} max={`${plan.end_date}T23:59`} defaultValue={localDue} /></label></div>
    <div className="form-grid"><label>Mục tiêu<select name="goal" defaultValue={initial?.goal_id ?? ""}><option value="">Việc hỗ trợ · không đo KPI</option>{plan.goals.map((g) => <option key={g.id} value={g.id}>{g.definition.name}</option>)}</select></label><label>Ưu tiên<select name="priority" defaultValue={initial?.priority ?? "NORMAL"}><option value="LOW">Thấp</option><option value="NORMAL">Bình thường</option><option value="HIGH">Cao</option></select></label></div>
    {confirm ? <div className="confirmation"><p>{String(confirm.title)} · {date(String(confirm.due_at))}. {initial ? "Lưu chỉnh sửa đề xuất chưa giao" : plan.is_manager ? "Giao cho nhân viên thực hiện" : "Gửi quản lý duyệt đề xuất"}.</p><button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate({path: initial ? `items/${initial.id}/draft` : `plans/${plan.id}/items`, body: confirm})}>Xác nhận {initial ? "lưu đề xuất" : plan.is_manager ? "giao việc" : "đề xuất"}</button><button className="secondary" type="button" onClick={() => setConfirm(null)}>Sửa lại</button></div> : <button>Xem lại công việc</button>}{mutation.isError && <WorkError error={mutation.error} />}
  </form>;
}

function History({plan, work, discussion = false}: {plan: string; work?: string; discussion?: boolean}) {
  const [page, setPage] = useState(1);
  const query = useQuery({queryKey: ["work-management", "history", plan, work, page], queryFn: () => workApi.history(plan, page, work)});
  return <div className="work-history"><h3>{discussion ? "Nội dung đã trao đổi" : "Lịch sử thao tác"}</h3>{query.isPending && <p>Đang tải lịch sử…</p>}{query.isError && <WorkError error={query.error} />}{query.data && <>{query.data.items.filter((e) => !discussion || ["comment", "plan_comment", "request_change", "plan_clarify"].includes(e.kind)).map((e) => <article key={e.id}><small>{date(e.created_at)} · {e.actor} · Kế hoạch bản {e.revision}</small><h4>{actionLabel[e.kind.replace("plan_", "")] ?? ({plan_saved: "Lưu phiên bản kế hoạch", created: "Tạo công việc"}[e.kind] ?? e.kind)}</h4>{e.body && <p className="work-prose">{e.body}</p>}</article>)}{!query.data.total && <p>Chưa có nội dung.</p>}<Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} /></>}</div>;
}

function RevisionHistory({plan}: {plan: string}) {
  const [open, setOpen] = useState(false), [page, setPage] = useState(1);
  const query = useQuery({queryKey: ["work-management", "revisions", plan, page], queryFn: () => workApi.revisions(plan, page), enabled: open});
  return <div><button className="secondary" onClick={() => setOpen(!open)}>{open ? "Ẩn các bản kế hoạch" : "Xem các phiên bản kế hoạch"}</button>{open && <>{query.isPending && <p>Đang tải phiên bản…</p>}{query.isError && <WorkError error={query.error} />}{query.data && <>{query.data.items.map((r) => <article className="work-card" key={r.number}><h4>Kế hoạch bản {r.number}</h4><small>{date(r.created_at)}</small><p className="work-prose">{r.objective}</p>{r.goals.map((g) => <details key={g.definition_id}><summary>{g.definition.name}: {g.target} {g.definition.unit} · {g.weight}%</summary><p>Ban đầu: {g.baseline} · {g.method}</p><p>Nguồn: {g.source}</p><p>Chuẩn nghiệm thu: {g.acceptance}</p>{g.numerator && <p>Tử: {g.numerator} · Mẫu: {g.denominator}</p>}{g.milestones.map((m) => <p key={m.title}>{m.title} · {m.weight}%</p>)}</details>)}</article>)}<Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} /></>}</>}</div>;
}
