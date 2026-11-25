"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useId, useState } from "react";
import { useAuth } from "../auth/auth-provider";
import { Pagination } from "../organization/shared";
import { workApi, type Work } from "../work-management/api";
import { progressApi, type Measurement, type Metric, type Metrics } from "./api";
import { CheckinDetail, CheckinEditor } from "./checkins";
import { Decision, displayDate, ErrorMessage, History, labels, localInput, ProgressModal, Tabs, useProgressCommand, type Dirty } from "./shared";

type Selection = {kind: "sources"; goal: Metric} | {kind: "new"; goal: Metric; work?: Work} |
  {kind: "measurement"; id: string; revision?: number} | {kind: "edit"; row: Measurement; goal: Metric} |
  {kind: "checkin"; id: string} | {kind: "new-checkin"} | {kind: "snapshots"} | {kind: "snapshot"; id: string} | null;

export function ProgressWorkspace({mode}: {mode: "measurements" | "checkins"}) {
  const {user} = useAuth();
  const router = useRouter();
  const cycle = useSearchParams().get("cycle_id") ?? undefined;
  const search = useSearchParams();
  const [planPage, setPlanPage] = useState(1), [page, setPage] = useState(1);
  const [planChoice, setPlanChoice] = useState("");
  const [window, setWindow] = useState<{from: string; to: string} | null>(null);
  const [selection, setSelection] = useState<Selection | undefined>();
  const allowed = !!user && ["EMPLOYEE", "MANAGER"].includes(user.role);
  const plans = useQuery({queryKey: ["work-management", "participants", planPage, cycle], queryFn: () => workApi.participants(planPage, cycle), enabled: allowed});
  const measurementId = search.get("measurement"), checkinId = search.get("checkin"), workId = search.get("work_source");
  const deepMeasurement = useQuery({queryKey: ["progress", "measurement", measurementId], queryFn: () => progressApi.measurement(measurementId!), enabled: allowed && !!measurementId});
  const deepCheckin = useQuery({queryKey: ["checkins", "detail", checkinId, 1], queryFn: () => progressApi.checkin(checkinId!), enabled: allowed && !!checkinId});
  const sourceWork = useQuery({queryKey: ["work-management", "item", workId, 1], queryFn: () => workApi.item(workId!), enabled: allowed && !!workId});
  const plan = planChoice || deepMeasurement.data?.plan_id || deepCheckin.data?.plan_id || sourceWork.data?.plan_id || search.get("plan_ref") || plans.data?.items.find((p) => p.plan_id)?.plan_id || "";
  const metrics = useQuery({queryKey: ["progress", "metrics", plan, window?.from, window?.to], queryFn: () => progressApi.metrics(plan, window?.from, window?.to), enabled: allowed && !!plan});
  const meetings = useQuery({queryKey: ["checkins", "list", plan, page], queryFn: () => progressApi.checkins(plan, page), enabled: allowed && !!plan && mode === "checkins"});
  const defaultGoal = metrics.data?.goals.find((g) => g.goal_id === sourceWork.data?.goal_id);
  const selected: Selection = selection !== undefined ? selection : measurementId ? {kind: "measurement", id: measurementId} : checkinId ? {kind: "checkin", id: checkinId} : search.get("snapshot") ? {kind: "snapshot", id: search.get("snapshot")!} : sourceWork.data && defaultGoal ? {kind: "new", goal: defaultGoal, work: sourceWork.data} : null;
  const close = () => {setSelection(null); router.replace(`/work-management?tab=${mode}&plan_ref=${plan}`, {scroll: false});};
  if (!allowed) return null;
  return <section className="auth-card wide work-area">
    <div className="section-heading"><div><h2>{mode === "measurements" ? "Số đo KPI có nguồn" : "Rà soát và hành động hỗ trợ"}</h2><p>{mode === "measurements" ? "Số đã xác minh trong kỳ · chưa phải điểm đánh giá." : "Chuẩn bị hai chiều, ghi nhận điều cần hỗ trợ và theo dõi ai đang giữ bước."}</p></div></div>
    <div className="filters"><label htmlFor="progress-plan">Kế hoạch cần theo dõi</label><select id="progress-plan" value={plan} onChange={(e) => {setPlanChoice(e.target.value); setWindow(null); setPage(1); setSelection(null);}}><option value="">Chọn kế hoạch</option>{plans.data?.items.filter((p) => p.plan_id).map((p) => <option key={p.plan_id} value={p.plan_id!}>{p.employee_name} · {p.cycle_name}</option>)}{plan && !plans.data?.items.some((p) => p.plan_id === plan) && <option value={plan}>Kế hoạch được mở từ thông báo</option>}</select></div>
    {metrics.data && mode === "measurements" && <DateWindow key={plan} data={metrics.data} active={window} apply={setWindow} />}
    {plans.data && plans.data.total > 20 && <Pagination page={planPage} total={plans.data.total} pending={plans.isFetching} onPage={setPlanPage} />}
    <ErrorMessage error={plans.error || metrics.error || deepMeasurement.error || deepCheckin.error || sourceWork.error} />
    {!plan && !plans.isPending && <div className="work-empty"><h3>Chưa có kế hoạch để theo dõi</h3><p>HR tổ chức kỳ theo tiến trình, quản lý lập kế hoạch và nhân viên xác nhận. Dữ liệu kỳ cũ vẫn ở các màn hình hiện tại.</p></div>}
    {plan && metrics.isPending && <p role="status">Đang tải tiến trình…</p>}
    {metrics.data && mode === "measurements" && <><div className="row-actions"><span>Lần cập nhật {metrics.data.measurement_version}</span><button className="secondary" onClick={() => setSelection({kind: "snapshots"})}>Lịch sử số liệu</button></div><div className="work-cards">{metrics.data.goals.map((g) => <article key={g.goal_id} className="work-card"><h3>{g.name}</h3><p>Mục tiêu: {g.target} {g.unit}</p><p className="metric-value">{g.actual !== null ? <><strong>{g.actual}</strong> {g.unit}<small>Đã xác minh · {g.source_count} nguồn</small></> : <strong>{g.data_status === "RULE_INCOMPATIBLE" ? "Cần kiểm tra cách đo đã duyệt" : "Chưa đủ dữ liệu xác minh"}</strong>}</p><p>{g.pending_count} bản khai đang soạn / chờ xử lý</p><div className="row-actions"><button className="secondary" onClick={() => setSelection({kind: "sources", goal: g})}>Xem các nguồn số đo</button>{metrics.data!.can_submit && g.data_status !== "RULE_INCOMPATIBLE" && <button onClick={() => setSelection({kind: "new", goal: g})}>Lập số đo</button>}</div></article>)}</div><p className="help-text">Nguồn nhập ngoài được quản lý xác minh nội bộ, chưa phải đối soát tự động với hệ thống bên ngoài. SUM là phần phát sinh; LAST là snapshot; tỷ lệ luôn có tử và mẫu.</p></>}
    {metrics.data && mode === "checkins" && <>{user?.role === "MANAGER" && metrics.data.manager_id === user.id && metrics.data.can_schedule && <button onClick={() => setSelection({kind: "new-checkin"})}>Lên lịch check-in</button>}<ErrorMessage error={meetings.error} />{meetings.isPending && <p role="status">Đang tải lịch…</p>}<div className="work-cards">{meetings.data?.items.map((c) => <article className="work-card" key={c.id}><small>{displayDate(c.scheduled_at)}</small><h3>{c.title}</h3><span className="work-badge">{labels[c.status]}</span><p>Rà soát: {c.period_start} → {c.period_end}</p>{c.overdue && <p className="work-warning">Đã qua lịch hẹn · quản lý cần điều phối</p>}{c.clarification_pending && <p>Cần quản lý phản hồi câu hỏi</p>}{c.status === "PUBLISHED" && c.acknowledged_publication !== c.publication && <p>Nhân viên chưa xác nhận đã đọc bản mới nhất</p>}<button onClick={() => setSelection({kind: "checkin", id: c.id})}>Mở check-in</button></article>)}</div>{meetings.data && !meetings.data.total && <p>Chưa có lịch check-in. Quản lý lên lịch tuần hoặc hai tuần để rà soát và hỗ trợ.</p>}{meetings.data && <Pagination page={page} total={meetings.data.total} pending={meetings.isFetching} onPage={setPage} />}</>}
    {selected?.kind === "sources" && <SourceList goal={selected.goal} close={close} open={(id) => setSelection({kind: "measurement", id})} />}
    {selected?.kind === "measurement" && <MeasurementDetail key={`${selected.id}:${selected.revision ?? "current"}`} id={selected.id} revision={selected.revision} editableGoalIds={metrics.data?.goals.map((g) => g.goal_id) ?? []} current={() => setSelection({kind: "measurement", id: selected.id})} close={close} edit={(row) => {const goal = metrics.data?.goals.find((g) => g.goal_id === row.goal_id); if (goal) setSelection({kind: "edit", row, goal});}} />}
    {(selected?.kind === "new" || selected?.kind === "edit") && metrics.data && <ProgressModal title={selected.kind === "new" ? "Lập số đo KPI" : "Đề nghị sửa / rút số đo"} close={close}>{(dirty) => <MeasurementEditor key={selected.kind === "edit" ? selected.row.id : selected.goal.goal_id} metrics={metrics.data!} goal={selected.goal} existing={selected.kind === "edit" ? selected.row : undefined} source={selected.kind === "new" ? selected.work : undefined} dirty={dirty} saved={(row) => setSelection({kind: "measurement", id: row.id})} />}</ProgressModal>}
    {selected?.kind === "new-checkin" && metrics.data && <ProgressModal title="Lên lịch check-in" close={close}>{(dirty) => <CheckinEditor metrics={metrics.data!} dirty={dirty} saved={(c) => setSelection({kind: "checkin", id: c.id})} />}</ProgressModal>}
    {selected?.kind === "checkin" && <CheckinDetail id={selected.id} close={close} />}
    {selected?.kind === "snapshots" && <SnapshotList plan={plan} close={close} open={(id) => setSelection({kind: "snapshot", id})} />}
    {selected?.kind === "snapshot" && <SnapshotDetail id={selected.id} close={close} open={(id, revision) => setSelection({kind: "measurement", id, revision})} />}
  </section>;
}

function SourceList({goal, close, open}: {goal: Metric; close: () => void; open: (id: string) => void}) {
  const [page, setPage] = useState(1);
  const query = useQuery({queryKey: ["progress", "measurements", goal.goal_id, page], queryFn: () => progressApi.measurements(goal.goal_id, page)});
  return <ProgressModal title={`Nguồn số đo · ${goal.name}`} close={close}>{() => <><ErrorMessage error={query.error} />{query.isPending && <p role="status">Đang tải nguồn…</p>}<div className="work-cards">{query.data?.items.map((m) => <article className="work-card" key={m.id}><h3>{m.source_key}</h3><span className="work-badge">{labels[m.status]}</span><p>{m.kind === "VOID" ? "Đề nghị rút cả dòng nguồn" : m.is_correction ? "Đề nghị thay thế số đã xác minh" : "Bản khai số liệu"}</p>{m.suspended && <p className="work-warning">Nguồn công việc đang bổ sung · không tính vào tổng hiện hành</p>}<p>Sự kiện: {displayDate(m.occurred_at)}</p><button onClick={() => open(m.id)}>Xem số đo</button></article>)}</div>{query.data && !query.data.total && <p>Chưa có nguồn nào. Nhân viên lập số đo từ kết quả đã có bằng chứng.</p>}{query.data && <Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} />}</>}</ProgressModal>;
}

function MeasurementDetail({id, close, edit, revision, current, editableGoalIds}: {id: string; close: () => void; edit: (row: Measurement) => void; revision?: number; current: () => void; editableGoalIds: string[]}) {
  const [tab, setTab] = useState(0), [page, setPage] = useState(1);
  const query = useQuery({queryKey: ["progress", "measurement", id, page, revision], queryFn: () => progressApi.measurement(id, page, revision)});
  const row = query.data;
  const evidence = row?.selected_revision ?? row;
  return <ProgressModal title="Chi tiết số đo KPI" close={close}>{(dirty) => <><ErrorMessage error={query.error} />{query.isPending && <p role="status">Đang tải số đo…</p>}{row && <><p className="eyebrow">{row.source_key} · Bản {row.selected_revision?.number ?? row.number} · {row.selected_revision ? "Đối chiếu lịch sử" : labels[row.status]}</p><Tabs prefix="measurement" names={["Nội dung", "Bằng chứng", "Lịch sử"]} active={tab} change={setTab} /><section role="tabpanel" id="measurement-panel-0" aria-labelledby="measurement-tab-0" hidden={tab !== 0}><p>Sự kiện: {displayDate(row.occurred_at)} · {row.source_kind === "WORK" ? "Từ công việc đã nghiệm thu" : "Nguồn nhập ngoài · xác minh nội bộ"}</p>{row.suspended && <p className="work-warning">Nguồn đang bị treo sau khi công việc mở lại. Cần nộp và xác minh lại với lần nghiệm thu mới.</p>}<MeasurementState row={row} /><HistoricalRevision row={row} current={current} />{revision === undefined && <NumericValues row={row} />}<p className="help-text">Giá trị đang đề nghị không tự thay thế số đã được xác minh.</p>{row.effective && <div className="work-card"><h4>Bản hiệu lực gần nhất: {row.effective.number}</h4><p>{row.effective.kind === "VOID" ? "Đã rút nguồn này khỏi tổng" : Object.entries(row.effective.payload).filter(([key]) => ["value", "numerator", "denominator"].includes(key)).map(([key, value]) => value !== null ? `${{value: "Giá trị", numerator: "Tử số", denominator: "Mẫu số"}[key]}: ${value}` : "").filter(Boolean).join(" · ")}</p>{row.suspended && <p>Bản này đang tạm ngừng đóng góp.</p>}</div>}{revision === undefined && row.actions.includes("draft") && <button className="secondary" disabled={!editableGoalIds.includes(row.goal_id)} onClick={() => edit(row)}>Sửa bản khai / đề nghị điều chỉnh</button>}{revision === undefined && <Decision path={`progress/measurements/${row.id}/actions`} version={row.version} actions={row.actions.filter((a) => a !== "draft")} dirty={dirty} />}</section><section role="tabpanel" id="measurement-panel-1" aria-labelledby="measurement-tab-1" hidden={tab !== 1}><h3>Bằng chứng bản {evidence?.number}</h3><p className="work-prose">{String(evidence?.payload.body ?? "")}</p>{evidence?.payload.url && <a href={String(evidence.payload.url)} target="_blank" rel="noopener noreferrer">Mở nguồn tham chiếu bên ngoài</a>}<h3>Các bản khai được giữ lại</h3>{row.revisions?.map((r) => <article className="work-card" key={r.id}><strong>Bản {r.number} · {r.kind === "VOID" ? "Rút nguồn" : "Giá trị"}</strong><small>{displayDate(r.created_at)}</small><p className="work-prose">{String(r.payload.body ?? "")}</p></article>)}</section><section role="tabpanel" id="measurement-panel-2" aria-labelledby="measurement-tab-2" hidden={tab !== 2}><History items={row.history?.items ?? []} /></section>{row.history && <Pagination page={page} total={Math.max(row.history.total, row.number)} pending={query.isFetching} onPage={setPage} />}</>}</>}</ProgressModal>;
}

function NumericValues({row}: {row: Measurement}) {
  if (row.kind === "VOID") return <p className="work-warning">{row.status === "VERIFIED" ? "Nguồn đã được rút khỏi tổng, không quay về giá trị cũ." : "Đề nghị rút toàn bộ nguồn, không quay về giá trị cũ."}</p>;
  if (row.method === "RATIO") return <p><strong>Tử số: {row.payload.numerator} / Mẫu số: {row.payload.denominator}</strong><br />Tổng KPI được tính từ tổng tử / tổng mẫu, không lấy trung bình các tỷ lệ.</p>;
  if (row.method === "MILESTONE") return <p>Mốc đã đạt: {(row.milestone ?? 0) + 1} trong kế hoạch đã duyệt.</p>;
  return <p><strong>{row.method === "SUM" ? "Phần phát sinh" : "Giá trị snapshot"}: {row.payload.value}</strong></p>;
}

function HistoricalRevision({row, current}: {row: Measurement; current: () => void}) {
  const selected = row.selected_revision;
  if (!selected) return null;
  return <article className="work-card"><h3>Bản nguồn đang đối chiếu: {selected.number}</h3><p>Nội dung dưới đây được giữ nguyên. Trạng thái và bản khai hiện hành có thể đã thay đổi.</p><NumericValues row={{...row, number: selected.number, kind: selected.kind, payload: selected.payload}} /><p className="work-prose">{String(selected.payload.body ?? "")}</p>{selected.payload.url && <p><a href={String(selected.payload.url)} target="_blank" rel="noopener noreferrer">Bằng chứng của đúng bản này</a></p>}<button type="button" className="secondary" onClick={current}>Mở bản hiện hành để xử lý</button></article>;
}

function MeasurementState({row}: {row: Measurement}) {
  return <>{row.next_actor && <p>Người giữ bước: {row.next_actor}</p>}{row.input_closed && ["DRAFT", "RETURNED"].includes(row.status) && <p className="work-warning">Đã qua hạn nộp. Bản khai được giữ để xử lý theo quy trình cuối kỳ; không tự điền số 0.</p>}</>;
}

export function MeasurementEditor({metrics, goal, existing, source, dirty, saved}: {metrics: Metrics; goal: Metric; existing?: Measurement; source?: Work; dirty: Dirty; saved: (row: Measurement) => void}) {
  const id = useId();
  const [kind, setKind] = useState("VALUE");
  const [sourceKind, setSourceKind] = useState(existing?.source_kind ?? (source ? "WORK" : "EXTERNAL_REFERENCE"));
  const [sourceKey, setSourceKey] = useState(existing?.source_key ?? source?.source_key ?? "");
  const [work, setWork] = useState(existing?.work_item_id ?? source?.id ?? "");
  const [workPage, setWorkPage] = useState(1);
  const [occurred, setOccurred] = useState(localInput(existing?.occurred_at));
  const [value, setValue] = useState(String(existing?.payload.value ?? ""));
  const [numerator, setNumerator] = useState(String(existing?.payload.numerator ?? ""));
  const [denominator, setDenominator] = useState(String(existing?.payload.denominator ?? ""));
  const [milestone, setMilestone] = useState(existing?.milestone !== null && existing?.milestone !== undefined ? String(existing.milestone) : "");
  const [body, setBody] = useState(String(existing?.payload.body ?? "")), [url, setUrl] = useState(String(existing?.payload.url ?? ""));
  const [review, setReview] = useState(false);
  const [expected, setExpected] = useState(existing?.version ?? metrics.plan_version);
  const latest = useQuery({queryKey: ["progress", "measurement", existing?.id, 1], queryFn: () => progressApi.measurement(existing!.id), enabled: !!existing});
  const stale = !!existing && !!latest.data && latest.data.version > expected;
  const accepted = useQuery({queryKey: ["work-management", "accepted", metrics.plan_id, workPage], queryFn: () => workApi.items(workPage, "ACCEPTED", "", metrics.plan_id), enabled: sourceKind === "WORK" && !existing && !source});
  const mutation = useProgressCommand<Measurement>((row) => {dirty(false); saved(row);});
  const mark = () => {dirty(true); setReview(false);};
  const field = {disabled: mutation.isPending};
  return <form className="work-form" onSubmit={(event) => {event.preventDefault(); setReview(true);}} onChange={mark}>
    {stale && <div className="work-warning" role="status">Số đo vừa được cập nhật. Bản nhập vẫn được giữ. <button type="button" onClick={() => {setExpected(latest.data!.version); setReview(false);}}>Đã xem trạng thái mới</button></div>}
    <h3>{goal.name}</h3><p>{goal.specification.source}</p>{existing && <><label htmlFor={`${id}-kind`}>Loại đề nghị</label><select id={`${id}-kind`} value={kind} onChange={(e) => setKind(e.target.value)} {...field}><option value="VALUE">Khai giá trị thay thế toàn phần</option>{existing.effective && <option value="VOID">Rút cả dòng nguồn có lý do</option>}</select></>}
    <label htmlFor={`${id}-source`}>Nguồn số liệu</label><select id={`${id}-source`} value={sourceKind} disabled={!!existing || !!source || mutation.isPending} onChange={(e) => {setSourceKind(e.target.value); setSourceKey(""); setWork("");}}><option value="EXTERNAL_REFERENCE">Hồ sơ / sự kiện ngoài có tham chiếu</option><option value="WORK">Công việc đã được nghiệm thu</option></select>
    {sourceKind === "WORK" && !existing && !source && <><label htmlFor={`${id}-work`}>Chọn công việc thuộc KPI này</label><select id={`${id}-work`} required value={work} {...field} onChange={(e) => {setWork(e.target.value); setSourceKey(accepted.data?.items.find((w) => w.id === e.target.value)?.source_key ?? "");}}><option value="">Chọn việc đã nghiệm thu</option>{accepted.data?.items.filter((w) => w.goal_id === goal.goal_id).map((w) => <option key={w.id} value={w.id}>{w.title} · {w.source_key}</option>)}</select><ErrorMessage error={accepted.error} />{accepted.data && accepted.data.total > 20 && <Pagination page={workPage} total={accepted.data.total} pending={accepted.isFetching} onPage={setWorkPage} />}</>}
    <label htmlFor={`${id}-key`}>Mã hồ sơ / sự kiện duy nhất</label><input id={`${id}-key`} required maxLength={120} value={sourceKey} readOnly={!!existing || sourceKind === "WORK"} {...field} onChange={(e) => setSourceKey(e.target.value)} /><p className="help-text">Không khai thêm một dòng cho cùng nguồn; không nhập lô tuần và lô tháng chồng lấn.</p>
    <label htmlFor={`${id}-time`}>Thời điểm sự kiện thực sự xảy ra</label><input id={`${id}-time`} type="datetime-local" required value={occurred} readOnly={!!existing} {...field} onChange={(e) => setOccurred(e.target.value)} />
    {kind === "VALUE" && (goal.method === "SUM" || goal.method === "LAST") && <><label htmlFor={`${id}-value`}>{goal.method === "SUM" ? "Giá trị phát sinh riêng của nguồn này" : "Giá trị snapshot tại thời điểm đo"} ({goal.unit})</label><input id={`${id}-value`} type="number" step="0.0001" min="0" max="1000000000000" required value={value} {...field} onChange={(e) => setValue(e.target.value)} /></>}
    {kind === "VALUE" && goal.method === "RATIO" && <><label htmlFor={`${id}-numerator`}>Tử số · {goal.specification.numerator}</label><input id={`${id}-numerator`} type="number" step="0.0001" min="0" required value={numerator} {...field} onChange={(e) => setNumerator(e.target.value)} /><label htmlFor={`${id}-denominator`}>Mẫu số · {goal.specification.denominator}</label><input id={`${id}-denominator`} type="number" step="0.0001" min="0" required value={denominator} {...field} onChange={(e) => setDenominator(e.target.value)} /></>}
    {goal.method === "MILESTONE" && <><label htmlFor={`${id}-milestone`}>Mốc theo kế hoạch đã duyệt</label><select id={`${id}-milestone`} required value={milestone} disabled={!!existing || mutation.isPending} onChange={(e) => setMilestone(e.target.value)}><option value="">Chọn mốc đạt</option>{goal.specification.milestones.map((m, index) => <option key={index} value={index}>{m.title} · {m.weight}%</option>)}</select></>}
    <label htmlFor={`${id}-body`}>{existing ? "Bằng chứng và lý do thay đổi / rút số" : "Mô tả bằng chứng và cách đối chiếu"}</label><textarea id={`${id}-body`} required maxLength={6000} value={body} {...field} onChange={(e) => setBody(e.target.value)} /><label htmlFor={`${id}-url`}>URL bằng chứng (không bắt buộc)</label><input id={`${id}-url`} type="url" pattern="https?://.*" value={url} {...field} onChange={(e) => setUrl(e.target.value)} />
    <ErrorMessage error={mutation.error} /><button type="submit" disabled={mutation.isPending}>Xem lại số đo</button>{review && <div className="confirmation"><p><strong>{sourceKey} · {kind === "VOID" ? "Đề nghị rút nguồn" : goal.method === "RATIO" ? `${numerator} / ${denominator}` : goal.method === "MILESTONE" ? `Mốc ${Number(milestone) + 1}` : value}</strong></p><p className="work-prose">{body}</p><p>Lưu thành bản khai; bạn tiếp tục nộp để quản lý xác minh. Chưa thay tổng số liệu đã xác minh.</p><button type="button" disabled={mutation.isPending || stale} onClick={() => mutation.mutate({path: existing ? `progress/measurements/${existing.id}/draft` : `progress/goals/${goal.goal_id}/measurements`, body: {expected_version: existing ? expected : metrics.plan_version, source_kind: sourceKind, source_key: sourceKey, work_item_id: sourceKind === "WORK" ? work : null, occurred_at: existing?.occurred_at ?? new Date(occurred).toISOString(), kind, milestone: goal.method === "MILESTONE" ? Number(milestone) : null, value: kind === "VALUE" && ["SUM", "LAST"].includes(goal.method) ? value : null, numerator: kind === "VALUE" && goal.method === "RATIO" ? numerator : null, denominator: kind === "VALUE" && goal.method === "RATIO" ? denominator : null, body, url: url || null}})}>Lưu bản khai</button><button type="button" className="secondary" onClick={() => setReview(false)}>Tiếp tục chỉnh sửa</button></div>}
  </form>;
}

function SnapshotList({plan, close, open}: {plan: string; close: () => void; open: (id: string) => void}) {
  const [page, setPage] = useState(1);
  const query = useQuery({queryKey: ["progress", "snapshots", plan, page], queryFn: () => progressApi.snapshots(plan, page)});
  return <ProgressModal title="Các lần tổng hợp được lưu" close={close}>{() => <><p>Mỗi lần thay đổi nguồn hiệu lực tạo một phiên bản. Sửa số hôm nay không viết lại bản cũ.</p><ErrorMessage error={query.error} />{query.data?.items.map((s) => <article className="work-card" key={s.id}><h3>Phiên bản {s.version}</h3><p>{displayDate(s.created_at)}</p><button onClick={() => open(s.id)}>Xem số liệu và nguồn tại mốc này</button></article>)}{query.data && !query.data.total && <p>Chưa có lần tổng hợp được lưu.</p>}{query.data && <Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} />}</>}</ProgressModal>;
}

function SnapshotDetail({id, close, open}: {id: string; close: () => void; open: (id: string, revision: number) => void}) {
  const [page, setPage] = useState(1);
  const query = useQuery({queryKey: ["progress", "snapshot", id, page], queryFn: () => progressApi.snapshot(id, page)});
  return <ProgressModal title="Số liệu tại thời điểm đã ghi nhận" close={close}>{() => <><ErrorMessage error={query.error} />{query.data && <><p>Phiên bản {query.data.version} · Đã biết lúc {displayDate(query.data.known_at)}</p>{query.data.goals.map((g) => <article className="work-card" key={g.goal_id}><h3>{g.name}</h3><p>{g.actual !== null ? `${g.actual} ${g.unit}` : "Chưa đủ dữ liệu xác minh"} · {g.source_count} nguồn</p></article>)}<h3>Nguồn được tính tại mốc này</h3>{query.data.sources.items.map((s) => <article className="work-card" key={s.measurement_id}><strong>{s.source_key} · bản {s.number}</strong><small>{displayDate(s.occurred_at)}</small><button className="secondary" onClick={() => open(s.measurement_id, s.number)}>Xem bản số đo và bằng chứng tại mốc này</button></article>)}<Pagination page={page} total={query.data.sources.total} pending={query.isFetching} onPage={setPage} /></>}</>}</ProgressModal>;
}

export function HRProgress({plan, close}: {plan: string; close: () => void}) {
  const query = useQuery({queryKey: ["progress", "coordination", plan], queryFn: () => progressApi.coordination(plan)});
  return <ProgressModal title="Điều phối tiến trình" close={close}>{() => <><p>HR theo dõi tình trạng để phối hợp. Nội dung bằng chứng và trao đổi riêng thuộc cặp quản lý–nhân viên.</p><ErrorMessage error={query.error} />{query.data && <><h3>{query.data.employee_name}</h3><HRReadiness data={query.data} />{(["measurements", "checkins", "actions"] as const).map((group) => <article className="work-card" key={group}><h4>{{measurements: "Số đo KPI", checkins: "Check-in", actions: "Hành động hỗ trợ"}[group]}</h4>{Object.entries(query.data![group]).map(([status, count]) => <p key={status}>{labels[status] ?? status}: {count}</p>)}{!Object.keys(query.data![group]).length && <p>Chưa phát sinh</p>}</article>)}</>}</>}</ProgressModal>;
}

function DateWindow({data, active, apply}: {data: Metrics; active: {from: string; to: string} | null; apply: (value: {from: string; to: string} | null) => void}) {
  const [from, setFrom] = useState(data.start_date ?? "");
  const [to, setTo] = useState(data.end_date ?? "");
  return <details className="work-card"><summary>Xem tiến trình theo khoảng ngày</summary><form className="filters" onSubmit={(e) => {e.preventDefault(); apply({from, to});}}><label>Từ ngày<input type="date" required min={data.start_date} max={data.end_date} value={from} onChange={(e) => setFrom(e.target.value)} /></label><label>Đến ngày<input type="date" required min={from} max={data.end_date} value={to} onChange={(e) => setTo(e.target.value)} /></label><button type="submit">Xem theo khoảng</button><button className="secondary" type="button" onClick={() => apply(null)}>Xem cả kỳ</button></form><p>{active ? `Đang xem ${active.from} → ${active.to}.` : "Đang xem cả kỳ."} SUM/RATIO dùng sự kiện trong khoảng; LAST/MILESTONE lấy lũy kế đến cuối khoảng. Mục tiêu hiển thị là mục tiêu cả kỳ.</p></details>;
}

function HRReadiness({data}: {data: {needs_hr: boolean; overdue: Record<string, number>}}) {
  return <>{data.needs_hr && <p className="work-warning">Cần kiểm tra tài khoản hoặc quan hệ quản lý. Quyền duyệt không tự chuyển sang HR.</p>}<p>Check-in quá lịch: {data.overdue?.checkins ?? 0} · Hỗ trợ quá hạn: {data.overdue?.actions ?? 0} · Số đo quá hạn xác minh: {data.overdue?.measurements ?? 0}</p></>;
}
