"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "../auth/auth-provider";
import { feedbackApi, type Assignment, type FeedbackInput } from "./api";
import { deadline, FeedbackError, relationships, statuses, SubmissionContent, useFeedbackRefresh, versions } from "./shared";

const schema = z.object({ rating: z.string().regex(/^[1-5]$/, "Chọn mức đánh giá từ 1 đến 5."),
  comment: z.string().max(2000, "Nhận xét tối đa 2.000 ký tự.").refine((v) => !/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(v), "Nhận xét chứa ký tự không hợp lệ.") });
type Values = z.infer<typeof schema>;
export function FeedbackDetail({ id }: { id: string }) {
  const { user } = useAuth();
  const query = useQuery({ queryKey: ["feedback", "mine", "detail", id, user?.id], queryFn: () => feedbackApi.detail(id), enabled: !!user });
  if (query.isPending) return <p role="status">Đang tải phân công…</p>;
  if (query.isError) return <FeedbackError error={query.error} reload={() => { void query.refetch(); }} />;
  if ("reviewer_id" in query.data && query.data.reviewer_id !== user?.id) return <section className="auth-card wide"><h1>Phân công của người khác</h1><p>HR có thể xem phản hồi gốc và quản trị phân công, nhưng chỉ chính người được giao mới gửi được phản hồi.</p><Link href={`/feedback-administration?participant_id=${query.data.participant_id}&cycle_id=${query.data.cycle_id}`}>Mở quản trị phân công</Link></section>;
  return <FeedbackForm initial={query.data} reload={async () => {
    const result = await query.refetch(); if (result.error) throw result.error; return result.data!;
  }} />;
}
function FeedbackForm({ initial, reload }: { initial: Assignment; reload: () => Promise<Assignment> }) {
  // Freeze versions until the author explicitly reloads. Background query refreshes
  // must never silently authorize submitting a draft against newer evidence.
  const [captured, setCaptured] = useState(initial), [confirmation, setConfirmation] = useState<Values | null>(null);
  const confirmationPanel = useRef<HTMLElement>(null);
  useEffect(() => { if (confirmation) { confirmationPanel.current?.focus(); confirmationPanel.current?.scrollIntoView?.({ block: "start", behavior: "smooth" }); } }, [confirmation]);
  const [reloadError, setReloadError] = useState<Error | null>(null), [loading, setLoading] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!captured.due_at || Date.parse(captured.due_at) <= now) return;
    const timer = setTimeout(() => setNow(Date.now()), Math.min(Math.max(0, Date.parse(captured.due_at) - Date.now()), 2_147_483_647));
    return () => clearTimeout(timer);
  }, [captured.due_at, now]);
  const cache = useQueryClient(), refresh = useFeedbackRefresh();
  const { user } = useAuth();
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { rating: "", comment: "" } });
  const mutation = useMutation({ mutationFn: (body: FeedbackInput) => feedbackApi.submit(body), onSuccess: (row) => {
    setCaptured(row); setConfirmation(null); cache.setQueryData(["feedback", "mine", "detail", row.id, user?.id], row); void refresh();
  } });
  const explicitReload = async () => {
    setLoading(true); setReloadError(null); setConfirmation(null);
    try { setCaptured(await reload()); mutation.reset(); } catch (error) { setReloadError(error as Error); }
    finally { setLoading(false); }
  };
  const row = captured, expired = !!row.due_at && now >= Date.parse(row.due_at);
  const canSubmit = row.status === "OPEN" && row.cycle_status === "ACTIVE" && !row.finalized && !expired;
  const text = useWatch({ control: form.control, name: "comment" });
  return <><section className="auth-card wide"><Link href="/feedback">← Phản hồi của tôi</Link><div className="section-heading"><div><p className="eyebrow">{relationships[row.relationship]}</p><h1>{row.employee_code} · {row.display_name}</h1></div><span className="badge">{statuses[row.status]}</span></div>
    <p>{row.cycle_name} · {row.start_date} – {row.end_date}</p><p>Hạn gửi: {deadline(row.due_at)} (theo múi giờ thiết bị).</p>
    <p className="help-text">Phân công gắn với tài khoản được HR giao. HR có thể xem nhận xét; kết quả tổng hợp cho nhân viên và quản lý được giới hạn theo quyền.</p></section>
    <section className="auth-card wide">
      {row.submission ? <><h2>Phản hồi đã được ghi nhận.</h2><SubmissionContent {...row.submission} /><p className="help-text">Đã gửi: {deadline(row.submission.submitted_at)}. Nội dung đã gửi không thể sửa.</p></> : <>
        {!canSubmit && <p role="status">{expired ? "Đã quá hạn. Hãy liên hệ HR để gia hạn." : "Phân công hiện không nhận phản hồi."}</p>}
        <form onSubmit={form.handleSubmit((values) => setConfirmation(values))}>
          <fieldset disabled={!canSubmit || mutation.isPending || loading}>
            <label htmlFor="feedback-rating">Mức đánh giá</label><select id="feedback-rating" {...form.register("rating")} aria-invalid={!!form.formState.errors.rating} aria-describedby="rating-help"><option value="">Chọn mức đánh giá</option>{[1, 2, 3, 4, 5].map((v) => <option value={v} key={v}>{v}/5</option>)}</select>
            <p id="rating-help" className="help-text">1 là thấp nhất, 5 là cao nhất. Đây là mức phản hồi, chưa phải điểm hiệu suất.</p>
            {form.formState.errors.rating && <p role="alert">{form.formState.errors.rating.message}</p>}
            <label htmlFor="feedback-comment">Nhận xét</label><textarea id="feedback-comment" rows={7} maxLength={2000} {...form.register("comment")} aria-describedby="comment-count" aria-invalid={!!form.formState.errors.comment} />
            <p id="comment-count" className="help-text">{text.length}/2.000 ký tự · Viết cụ thể, rõ ràng; tránh đưa thông tin cá nhân không cần thiết.</p>
            {form.formState.errors.comment && <p role="alert">{form.formState.errors.comment.message}</p>}
            {canSubmit && <button disabled={mutation.isPending}>Kiểm tra và gửi</button>}
          </fieldset>
        </form>
        {confirmation && canSubmit && <section ref={confirmationPanel} tabIndex={-1} className="confirmation" aria-label="Xác nhận gửi phản hồi"><h2>Kiểm tra trước khi gửi</h2><SubmissionContent rating={Number(confirmation.rating)} comment={confirmation.comment} /><p>Chỉ gửi một lần. Sau khi gửi, bạn không thể sửa hoặc xóa.</p><div className="row-actions"><button disabled={mutation.isPending} onClick={() => mutation.mutate({ assignment_id: row.id, ...versions(row), rating: Number(confirmation.rating), comment: confirmation.comment })}>Xác nhận gửi một lần</button><button className="secondary" disabled={mutation.isPending} onClick={() => setConfirmation(null)}>Quay lại chỉnh sửa</button></div></section>}
      </>}
      {mutation.isError && <FeedbackError error={mutation.error} reload={() => { void explicitReload(); }} />}
      {reloadError && <FeedbackError error={reloadError} reload={() => { void explicitReload(); }} />}
      {loading && <p role="status">Đang kiểm tra phiên bản mới…</p>}
    </section></>;
}
