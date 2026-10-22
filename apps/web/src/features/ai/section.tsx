"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiClientError } from "../../lib/api-client";
import { useAuth } from "../auth/auth-provider";
import { Pagination } from "../organization/shared";
import type { Report } from "../performance/api";
import { aiApi, type Analysis, type Audience, type Intent } from "./api";

const errors: Record<string, string> = {
  ai_not_configured: "Gemini chưa được cấu hình. Điểm số và các chức năng khác vẫn sử dụng bình thường.",
  provider_timeout: "Gemini phản hồi quá thời gian. Bạn có thể kiểm tra yêu cầu vừa gửi hoặc thử lại chủ động.",
  provider_quota: "Gemini đang giới hạn lượt sử dụng. Hãy chờ rồi thử lại.",
  provider_unavailable: "Tạm thời không kết nối được Gemini.",
  provider_configuration: "Cấu hình Gemini chưa phù hợp. Người vận hành cần kiểm tra key và model.",
  provider_invalid_output: "Phản hồi AI chưa đạt định dạng yêu cầu nên chưa được lưu thành tư vấn.",
  provider_blocked: "Gemini chưa trả được nội dung hoàn chỉnh. Bạn có thể thử lại sau.",
  analysis_stale: "Dữ liệu đã thay đổi trong lúc tạo tư vấn. Hãy kiểm tra kết quả mới trước khi tạo lại.",
  review_stale: "Cần tính lại điểm trước khi tạo tư vấn AI.",
  stale_calculation_version: "Đã có lần tính mới. Hãy tải lại dữ liệu.",
  stale_evidence_version: "Bằng chứng đã thay đổi. Hãy tải lại dữ liệu.",
  stale_analysis_version: "Đã có tư vấn mới. Hãy tải lại và kiểm tra trước khi tạo lại.",
  generation_in_progress: "Đang có yêu cầu AI cho hồ sơ này. Hãy chờ hoặc làm mới trạng thái.",
  generation_cooldown: "Cần chờ ít nhất 30 giây giữa hai lượt tạo tư vấn của cùng hồ sơ.",
  generation_expired: "Yêu cầu trước đã quá hạn. HR có thể chủ động tạo một yêu cầu mới.",
  idempotency_conflict: "Mã yêu cầu thuộc một thao tác khác. Hãy tải lại dữ liệu trước khi tạo mới.",
  authority_changed: "Quyền truy cập đã thay đổi nên kết quả AI không được công bố.",
};
function ErrorMessage({ error }: { error: Error }) {
  return <p role="alert">{error instanceof ApiClientError ? errors[error.code] ?? "Không thể thực hiện yêu cầu. Hãy làm mới dữ liệu và kiểm tra phiên đăng nhập." : "Mất kết nối. Kiểm tra yêu cầu vừa gửi trước khi tạo yêu cầu mới."}</p>;
}

export function AISection({ report }: { report: Report }) {
  const { user } = useAuth();
  const [selected, setSelected] = useState<Audience>("PUBLIC");
  if (!user || user.role === "ADMIN" || !report.review_id) return null;
  const audience = user.role === "HR" ? selected : "PUBLIC";
  return <section className="auth-card wide ai-panel"><div className="section-heading"><div><p className="eyebrow">GÓC NHÌN THAM KHẢO</p><h2>Tư vấn AI</h2></div><span className="badge">Không thay đổi điểm số</span></div>
    <p>AI hỗ trợ diễn giải bằng chứng và gợi ý hành động. Nội dung cần được người dùng xem xét trước khi áp dụng.</p>
    {user.role === "HR" && <div className="ai-scope-switch" role="group" aria-label="Phạm vi tư vấn"><button className={audience === "PUBLIC" ? "" : "secondary"} aria-pressed={audience === "PUBLIC"} onClick={() => setSelected("PUBLIC")}>Tư vấn chung</button><button className={audience === "HR_PRIVATE" ? "" : "secondary"} aria-pressed={audience === "HR_PRIVATE"} onClick={() => setSelected("HR_PRIVATE")}>Nội bộ HR</button></div>}
    <Panel key={`${user.id}-${report.review_id}-${audience}`} report={report} audience={audience} userId={user.id} hr={user.role === "HR"} />
  </section>;
}

function readIntent(key: string, audience: Audience): Intent | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(key) ?? "null");
    if (!value || typeof value !== "object") return null;
    const data = value as Partial<Intent>;
    if (typeof data.client_request_id !== "string" || !/^[0-9a-f-]{36}$/i.test(data.client_request_id) || data.audience !== audience || typeof data.regenerate !== "boolean" || !Number.isInteger(data.expected_calculation_version) || !Number.isInteger(data.expected_evidence_version)) return null;
    if (data.expected_calculation_version! < 1 || data.expected_evidence_version! < 1 || (data.regenerate && (!Number.isInteger(data.expected_latest_generation) || data.expected_latest_generation! < 0))) return null;
    return { client_request_id: data.client_request_id, audience, regenerate: data.regenerate, expected_calculation_version: data.expected_calculation_version!, expected_evidence_version: data.expected_evidence_version!, ...(data.regenerate ? { expected_latest_generation: data.expected_latest_generation! } : {}) };
  } catch { return null; }
}

function Panel({ report, audience, userId, hr }: { report: Report; audience: Audience; userId: string; hr: boolean }) {
  const cache = useQueryClient(), review = report.review_id!;
  const storageKey = `insighthr-ai-intent:${userId}:${review}:${audience}`;
  const query = useQuery({ queryKey: ["ai", "state", userId, review, audience], queryFn: () => aiApi.state(review, audience) });
  const [intent, setIntent] = useState<Intent | null>(() => hr ? readIntent(storageKey, audience) : null);
  const [sent, setSent] = useState(() => hr && readIntent(storageKey, audience) !== null);
  const [ack, setAck] = useState(false), [history, setHistory] = useState(false);
  const refresh = () => cache.invalidateQueries({ queryKey: ["ai"] });
  const remember = (value: Intent | null) => { try { if (value) sessionStorage.setItem(storageKey, JSON.stringify(value)); else sessionStorage.removeItem(storageKey); } catch { /* No persistence support: retain the intent in component state. */ } };
  const mutation = useMutation({ retry: false, mutationFn: (value: Intent) => { remember(value); setSent(true); return aiApi.generate(review, value); }, onSuccess: async (row) => { if (row.status !== "RUNNING") { remember(null); setIntent(null); setAck(false); setSent(false); } await refresh(); }, onError: () => { void refresh(); } });
  if (query.isPending) return <p role="status">Đang tải trạng thái tư vấn…</p>;
  if (query.isError) return <><ErrorMessage error={query.error} /><button className="secondary" onClick={() => { void query.refetch(); }}>Thử tải lại tư vấn</button></>;
  const data = query.data;
  const fresh = !!report.current_result && ["CURRENT", "FINALIZED"].includes(report.state);
  const mismatch = !!intent && (intent.expected_evidence_version !== report.evidence_version || intent.expected_calculation_version !== report.current_result?.calculation_version || (intent.regenerate && intent.expected_latest_generation !== (data.current_analysis?.generation_version ?? 0)));
  const open = () => { const regenerate = !!data.current_analysis; setIntent({ client_request_id: crypto.randomUUID(), expected_calculation_version: report.current_result!.calculation_version, expected_evidence_version: report.evidence_version, audience, regenerate, ...(regenerate ? { expected_latest_generation: data.current_analysis!.generation_version } : {}) }); setSent(false); setAck(false); mutation.reset(); };
  const clear = () => { remember(null); setIntent(null); setSent(false); setAck(false); mutation.reset(); };
  return <>
    {audience === "HR_PRIVATE" && <p className="state-notice">Phân tích nhận xét nội bộ — chỉ HR có quyền xem. Nhận xét được che thông tin trước khi gửi; không cam kết ẩn danh tuyệt đối.</p>}
    {!data.configured && <p className="state-notice">Gemini chưa được cấu hình. Bạn vẫn xem được tư vấn đã lưu; điểm số và các chức năng khác hoạt động bình thường.</p>}
    {!fresh && <p className="state-notice">Cần tính lại điểm trước khi tạo tư vấn AI. Nội dung cũ chỉ dùng để đối chiếu lịch sử.</p>}
    {data.current_analysis ? <AnalysisContent row={data.current_analysis} /> : data.last_successful_analysis ? <p className="state-notice">Có tư vấn thuộc lần tính trước. Mở lịch sử để đối chiếu; nội dung đó chưa phải tư vấn cho điểm hiện tại.</p> : <p>Chưa có tư vấn được lưu trong phạm vi này.</p>}
    {data.latest_attempt?.status === "RUNNING" && <p role="status">Đang xử lý yêu cầu AI. Bạn có thể làm mới trạng thái; thao tác này không tạo thêm yêu cầu.</p>}
    {data.latest_attempt?.status === "FAILED" && <p className="state-notice">{errors[data.latest_attempt.error_code ?? ""] ?? "Lần tạo gần nhất chưa thành công."} Tư vấn đã lưu trước đó vẫn được giữ.</p>}
    <div className="row-actions"><button className="secondary" disabled={query.isFetching || mutation.isPending} onClick={() => { void refresh(); }}>Làm mới tư vấn</button>{hr && data.can_generate && fresh && !intent && <button onClick={open}>{data.current_analysis ? "Tạo lại tư vấn AI" : "Tạo tư vấn AI"}</button>}<button className="secondary" onClick={() => setHistory((value) => !value)}>{history ? "Ẩn lịch sử AI" : "Xem lịch sử AI"}</button></div>
    {hr && intent && <section className="confirmation" role="group" aria-label="Xác nhận tạo tư vấn AI"><h3>{intent.regenerate ? "Tạo lại tư vấn" : "Tạo tư vấn"} · {audience === "PUBLIC" ? "Dùng chung" : "Nội bộ HR"}</h3>
      <p>{audience === "PUBLIC" ? "Gửi điểm số, dữ liệu KPI và thống kê phản hồi đã lọc. Không gửi nhận xét hay danh tính." : "Gửi dữ liệu số và tối đa 20 nhận xét đã che thông tin của đúng lần tính. Dữ liệu có thể được chọn mẫu hoặc rút ngắn."} Dịch vụ Gemini có thể tính phí; kết quả trước vẫn được giữ nếu lần này lỗi.</p>
      {mismatch && <p role="alert">Dữ liệu xác nhận đã thay đổi. Kiểm tra yêu cầu cũ hoặc đóng xác nhận và làm mới trước khi tạo mới.</p>}
      {!sent && <label className="checkbox-label"><input type="checkbox" checked={ack} disabled={mutation.isPending} onChange={(event) => setAck(event.target.checked)} />Tôi đã kiểm tra phạm vi dữ liệu và đồng ý gửi yêu cầu.</label>}
      <div className="row-actions">{sent ? <button disabled={mutation.isPending} onClick={() => mutation.mutate(intent)}>Kiểm tra yêu cầu vừa gửi</button> : <button disabled={!ack || mismatch || mutation.isPending || mutation.isError} onClick={() => mutation.mutate(intent)}>Xác nhận tạo tư vấn</button>}<button className="secondary" disabled={mutation.isPending} onClick={clear}>{sent ? "Đóng và kiểm tra lại trước khi tạo mới" : "Hủy"}</button></div>
      {mutation.isPending && <p role="status">Đang gửi yêu cầu… Không cần bấm tạo thêm.</p>}{mutation.isError && <ErrorMessage error={mutation.error} />}
    </section>}
    {history && <History review={review} audience={audience} userId={userId} />}
  </>;
}

function AnalysisContent({ row }: { row: Analysis }) {
  if (!row.output) return <p>{row.error_code ? errors[row.error_code] ?? "Yêu cầu chưa có nội dung tư vấn." : "Yêu cầu đang xử lý."}</p>;
  return <article className="ai-result"><p className="help-text">Lần tư vấn {row.generation_version} · Lần tính {row.calculation_version} · {row.model} · {row.generated_at ? new Date(row.generated_at).toLocaleString("vi-VN") : ""}</p><p className="plain-comment">{row.output.summary}</p>
    <div className="feedback-cards">{([["strengths", "Điểm mạnh"], ["improvement_areas", "Điểm cần cải thiện"], ["feedback_themes", "Góc nhìn phản hồi"], ["recommended_actions", "Hành động đề xuất"], ["caveats", "Giới hạn và lưu ý"]] as const).map(([field, title]) => <section className="inbox-card" key={field}><h3>{title}</h3>{row.output![field].length ? <ul>{row.output![field].map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>Chưa có đủ bằng chứng để đưa ra nhận định.</p>}</section>)}</div>
    {row.input_sampled && <p className="state-notice">Đầu vào đã được chọn mẫu hoặc rút ngắn; phân tích không bao phủ toàn bộ nhận xét.</p>}
  </article>;
}

function History({ review, audience, userId }: { review: string; audience: Audience; userId: string }) {
  const [page, setPage] = useState(1), [selected, setSelected] = useState<string | null>(null);
  const query = useQuery({ queryKey: ["ai", "history", userId, review, audience, page], queryFn: () => aiApi.history(review, audience, page) });
  const detail = useQuery({ queryKey: ["ai", "detail", userId, review, audience, selected], queryFn: () => aiApi.detail(review, selected!), enabled: selected !== null });
  return <section className="ai-history"><h3>Lịch sử tư vấn · {audience === "PUBLIC" ? "Dùng chung" : "Nội bộ HR"}</h3>
    {query.isPending && <p role="status">Đang tải lịch sử AI…</p>}{query.isError && <ErrorMessage error={query.error} />}
    {query.data && <>{!query.data.items.length && <p>Chưa có lịch sử tư vấn.</p>}<div className="table-scroll"><table><caption>Các lần yêu cầu, mới nhất trước</caption><thead><tr><th>Lần tư vấn</th><th>Lần tính</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>{query.data.items.map((row) => <tr key={row.id}><td>{row.generation_version}</td><td>{row.calculation_version}</td><td>{row.status === "SUCCEEDED" ? "Đã lưu" : row.status === "RUNNING" ? "Đang xử lý" : "Chưa thành công"}</td><td><button className="secondary" onClick={() => setSelected(row.id)}>Xem tư vấn {row.generation_version}</button></td></tr>)}</tbody></table></div><Pagination page={page} total={query.data.total} pending={query.isFetching} onPage={setPage} /></>}
    {selected && <div className="state-notice"><h3>Đang xem tư vấn lịch sử</h3><button className="secondary" onClick={() => setSelected(null)}>Đóng tư vấn lịch sử</button>{detail.isPending && <p role="status">Đang tải nội dung…</p>}{detail.isError && <ErrorMessage error={detail.error} />}{detail.data && <AnalysisContent row={detail.data} />}</div>}
  </section>;
}
