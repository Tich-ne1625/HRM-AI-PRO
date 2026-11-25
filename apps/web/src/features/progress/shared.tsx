"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState, type ReactNode } from "react";
import { ApiClientError } from "../../lib/api-client";
import { WorkspaceDialog } from "../workspace/dialog";
import { progressApi, type Event } from "./api";

export type Dirty = (dirty: boolean, source?: string) => void;
export const labels: Record<string, string> = {
  DRAFT: "Đang soạn", SUBMITTED: "Chờ xác minh", VERIFIED: "Đã xác minh", RETURNED: "Cần bổ sung",
  REJECTED: "Chưa chấp nhận", SCHEDULED: "Đã lên lịch", OPEN: "Đang trao đổi", PUBLISHED: "Đã công bố",
  CANCELLED: "Đã hủy", IN_PROGRESS: "Đang thực hiện", CHANGES_REQUESTED: "Cần bổ sung", DONE: "Đã hoàn thành",
  submit: "Nộp để kiểm tra", verify: "Xác minh số liệu", return: "Yêu cầu bổ sung", reject: "Không chấp nhận",
  open: "Mở buổi rà soát", publish: "Công bố biên bản", acknowledge: "Xác nhận đã đọc",
  clarify: "Yêu cầu làm rõ", addendum: "Công bố phụ lục", reschedule: "Đổi lịch hẹn", cancel: "Hủy có lý do",
  start: "Bắt đầu thực hiện", complete: "Xác nhận đã hoàn thành",
};
export const displayDate = (value: string) => new Date(value).toLocaleString("vi-VN");
export const localInput = (value = new Date().toISOString()) => {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

export function ErrorMessage({error}: {error: Error | null}) {
  if (!error) return null;
  const messages: Record<string, string> = {
    stale_version: "Dữ liệu đã thay đổi. Bản nhập được giữ lại; xem trạng thái mới trước khi gửi.",
    duplicate_measurement_source: "Nguồn, mốc hoặc thời điểm này đã có số đo. Mở dòng cũ để đề nghị sửa, không tạo thêm.",
    measurement_source_frozen: "Nguồn đã gửi không được đổi. Đề nghị rút nguồn sai rồi lập nguồn đúng.",
    measurement_rule_incompatible: "Cách đo chưa tương thích với đơn vị hoặc target đã duyệt. Cần xử lý kế hoạch theo quy trình, không tự sửa số.",
    source_not_accepted: "Công việc phải được nghiệm thu trước khi nộp hoặc xác minh số đo.",
    source_revision_changed: "Công việc đã có lần nghiệm thu mới. Lưu bản số đo mới để kiểm tra lại nguồn.",
    invalid_measurement: "Kiểm tra trường số liệu đúng cách đo. Tỷ lệ cần cả tử và mẫu, tử không vượt mẫu.",
    invalid_measurement_time: "Thời điểm sự kiện phải nằm trong kỳ và không ở tương lai.",
    invalid_source: "Kiểm tra mã nguồn và công việc gắn đúng mục tiêu.",
    workflow_cutoff: "Đã qua hạn xử lý. Nội dung vẫn được giữ; liên hệ HR để điều phối theo quy trình cuối kỳ.",
    work_not_found: "Không tìm thấy nội dung trong phạm vi của bạn.",
    work_not_ready: "Kế hoạch phải được duyệt, xác nhận và kỳ đã kích hoạt.",
    work_accounts_required: "Tài khoản hoặc quản lý cần HR kiểm tra. Quyền xử lý không tự chuyển.",
    forbidden: "Bạn không có quyền thực hiện bước này.",
    validation_error: "Kiểm tra các trường bắt buộc, kiểu số và thời gian.",
    invalid_action_deadline: "Hạn hỗ trợ phải ở tương lai và không sau hạn xác minh của kỳ.",
    invalid_checkin_schedule: "Chọn lịch hẹn ở tương lai và trước hạn xác minh của kỳ.",
  };
  return <p role="alert" className="work-error">{error instanceof ApiClientError ? messages[error.code] ?? "Bước xử lý đã thay đổi hoặc dữ liệu chưa hợp lệ. Kiểm tra trạng thái rồi thử lại." : "Chưa kết nối được. Bản nhập vẫn được giữ; thử lại khi có mạng."}</p>;
}

export function useProgressCommand<T>(saved: (data: T) => void) {
  const cache = useQueryClient();
  const request = useRef<{signature: string; id: string} | null>(null);
  return useMutation({mutationFn: ({path, body}: {path: string; body: Record<string, unknown>}) => {
    const signature = JSON.stringify({path, body});
    if (request.current?.signature !== signature) request.current = {signature, id: crypto.randomUUID()};
    return progressApi.write<T>(path, {...body, client_request_id: request.current.id});
  }, onSuccess: async (data) => {
    request.current = null;
    saved(data);
    await Promise.all(["progress", "checkins", "work-management", "notifications", "dashboard"].map((key) => cache.invalidateQueries({queryKey: [key]})));
  }});
}

export function ProgressModal({title, close, children}: {title: string; close: () => void; children: (dirty: Dirty) => ReactNode}) {
  const [sources, setSources] = useState<Set<string>>(new Set());
  const [discard, setDiscard] = useState(false);
  const mark: Dirty = (value, source = "form") => setSources((old) => {const next = new Set(old); if (value) next.add(source); else next.delete(source); return next;});
  return <WorkspaceDialog title={title} eyebrow="TIẾN TRÌNH & PHỐI HỢP" variant="content" close={() => sources.size ? setDiscard(true) : close()}>
    <div className="work-area">{discard && <div role="alert" className="confirmation"><p>Bạn có nội dung chưa lưu. Đóng sẽ bỏ bản nhập.</p><button onClick={close}>Bỏ bản nhập và đóng</button><button className="secondary" onClick={() => setDiscard(false)}>Tiếp tục chỉnh sửa</button></div>}{children(mark)}</div>
  </WorkspaceDialog>;
}

export function Tabs({names, active, change, prefix}: {names: string[]; active: number; change: (value: number) => void; prefix?: string}) {
  const generated = useId();
  const id = prefix ?? generated;
  return <div role="tablist" className="work-tabs" aria-label="Nội dung chi tiết" onKeyDown={(event) => {
    const next = event.key === "ArrowRight" ? (active + 1) % names.length : event.key === "ArrowLeft" ? (active + names.length - 1) % names.length : event.key === "Home" ? 0 : event.key === "End" ? names.length - 1 : null;
    if (next !== null) {event.preventDefault(); change(next); event.currentTarget.querySelectorAll<HTMLButtonElement>("button")[next]?.focus();}
  }}>{names.map((name, index) => <button key={name} id={`${id}-tab-${index}`} aria-controls={`${id}-panel-${index}`} type="button" role="tab" aria-selected={active === index} tabIndex={active === index ? 0 : -1} onClick={() => change(index)}>{name}</button>)}</div>;
}

export function History({items}: {items: Event[]}) {
  const eventLabel = (kind: string) => {
    const action = kind.split(".").at(-1) ?? kind;
    return labels[action] ?? ({create: "Tạo mới", draft: "Lưu bản khai", prepare: "Chuẩn bị check-in", suspended: "Tạm ngừng tính nguồn công việc"}[action as "create"] ?? "Cập nhật tiến trình");
  };
  return <div className="work-cards">{items.map((event) => <article className="work-card" key={event.id}><strong>{eventLabel(event.kind)}</strong><small>{displayDate(event.created_at)}</small>{event.body && <p className="work-prose">{event.body}</p>}</article>)}{!items.length && <p>Chưa có sự kiện được chia sẻ.</p>}</div>;
}

export function Decision({path, version, actions, dirty, publication, saved}: {path: string; version: number; actions: string[]; dirty: Dirty; publication?: number; saved?: () => void}) {
  const id = useId();
  const [selected, setSelected] = useState("");
  const [body, setBody] = useState("");
  const [scheduled, setScheduled] = useState("");
  const [expected, setExpected] = useState(version);
  const [review, setReview] = useState(false);
  const action = selected || actions[0] || "";
  const dirtyKey = `${path}:${id}`;
  const hasInput = !!body || !!selected || !!scheduled || review;
  const baseVersion = hasInput ? expected : version;
  const mutation = useProgressCommand<{version: number}>((data) => {setExpected(data.version); dirty(false, dirtyKey); setBody(""); setScheduled(""); setSelected(""); setReview(false); saved?.();});
  const changed = version > baseVersion;
  const permitted = actions.includes(action);
  const needsBody = path.startsWith("checkin-actions/") || !["open", "acknowledge", "start", "submit"].includes(action);
  const disabled = mutation.isPending || changed || !permitted;
  if (!action && !body) return <p className="help-text">Không có thao tác đang chờ bạn ở bước này.</p>;
  return <form className="work-form" onSubmit={(event) => {event.preventDefault(); if (!disabled) {if (!hasInput) setExpected(version); setReview(true);}}}>
    {changed && <div role="status" className="work-warning">Có cập nhật mới. Bản nhập được giữ. <button type="button" onClick={() => {setExpected(version); setReview(false);}}>Đã xem trạng thái mới</button></div>}
    <label htmlFor={`${id}-action`}>Bước cần thực hiện</label><select id={`${id}-action`} value={action} disabled={mutation.isPending} onChange={(e) => {if (!hasInput) setExpected(version); setSelected(e.target.value); setReview(false); dirty(true, dirtyKey);}}>{!permitted && <option value={action}>{labels[action]} · không còn khả dụng</option>}{actions.map((a) => <option key={a} value={a}>{labels[a] ?? a}</option>)}</select>
    <label htmlFor={`${id}-body`}>{needsBody ? "Nhận xét / nội dung quyết định" : "Trao đổi thêm (không bắt buộc)"}</label><textarea id={`${id}-body`} required={needsBody} maxLength={6000} value={body} disabled={mutation.isPending} onChange={(e) => {if (!hasInput) setExpected(version); setBody(e.target.value); setReview(false); dirty(!!e.target.value || !!selected || !!scheduled, dirtyKey);}} />
    {action === "reschedule" && <><label htmlFor={`${id}-scheduled`}>Lịch hẹn mới</label><input id={`${id}-scheduled`} type="datetime-local" required value={scheduled} disabled={mutation.isPending} onChange={(e) => {if (!hasInput) setExpected(version); setScheduled(e.target.value); setReview(false); dirty(true, dirtyKey);}} /></>}
    <ErrorMessage error={mutation.error} /><button disabled={disabled} type="submit">Xem lại trước khi gửi</button>
    {review && <div className="confirmation"><p><strong>{labels[action]}</strong></p><p className="work-prose">{body || "Xác nhận thực hiện bước đã chọn."}</p><button type="button" disabled={disabled} onClick={() => mutation.mutate({path, body: {action, expected_version: baseVersion, body: body || undefined, ...(publication !== undefined ? {publication} : {}), ...(action === "reschedule" ? {scheduled_at: new Date(scheduled).toISOString()} : {})}})}>Xác nhận gửi</button><button type="button" className="secondary" disabled={mutation.isPending} onClick={() => setReview(false)}>Tiếp tục chỉnh sửa</button></div>}
  </form>;
}
