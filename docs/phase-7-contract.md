# Hợp đồng Phase 7 — Tư vấn Gemini theo quyền

Ngày: 2026-10-22. Trạng thái: **đã triển khai và nghiệm thu offline/CI; chưa nghiệm thu Gemini thật**. Tham chiếu [kiến trúc](architecture.md), [AI design](ai-design.md), [Phase 6](phase-6-contract.md), [review](phase-7-review.md) và [kế hoạch triển khai](superpowers/plans/2026-10-22-phase-7-gemini.md).

## 1. Cơ sở và phạm vi

Source lúc đối chiếu: `8bf384bff3a5af6019c3aaf26c30383cdb474686`, repository clean và đồng bộ origin/main. Runtime Phase 6 `f595f23` đã qua [CI 39715137000](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39715137000): 767 backend/104 web tests, Ruff/mypy/lint/types/build và Docker smoke/persistence. Đây là bằng chứng nghiệm thu trước đó, không phải chạy lại trong lượt lập kế hoạch.

Đã có PerformanceReview, immutable revisions, evidence hash/version, frozen policy, live report SQL scope, HR finalization và cycle closure. Chưa có AIAnalysis, provider adapter, SDK/key/model settings, generation lease hoặc giao diện AI. Revision Phase 6 không chứa comment; chỉ chứa assignment membership và ratings riêng tư. Không được gửi nguyên `evidence_snapshot` hoặc public presenter cho provider mà không xây input allowlist riêng.

Phase 7 thêm tư vấn bằng Gemini, lưu kết quả và lịch sử, chủ động tạo lại, xử lý provider lỗi và kết quả cũ. Điểm deterministic, quy tắc chốt/đóng kỳ giữ nguyên. Không chatbot, agent/tools, streaming, queue, dashboard/chart, seed, tự động chấm điểm, quyết định lương/thăng chức/kỷ luật hoặc sửa điểm bằng AI.

## 2. Hai phạm vi tư vấn, một nền tảng generation

Đây là đề xuất cụ thể hóa ranh giới privacy của kiến trúc: không dùng chung một output được suy ra từ nhận xét riêng tư cho mọi role. Yêu cầu prompt “đừng tiết lộ” không đủ để làm ranh giới phân quyền.

| Audience | Đầu vào | Quyền xem kết quả |
| --- | --- | --- |
| `PUBLIC` | Điểm/KPI bằng số, policy, count/mean và groups đã suppression; **không comment**, reviewer identity hoặc nhãn tổ chức/cá nhân | HR, nhân viên của chính mình, quản lý trực tiếp hiện tại qua live SQL scope |
| `HR_PRIVATE` | Cùng dữ liệu số và nhận xét đã khử định danh từ submitted membership của đúng revision | Chỉ HR, qua DTO/cache/query riêng |

Chỉ HR tạo/tạo lại cả hai audience. ADMIN không kế thừa HR, reviewer không nhận report quyền nhờ assignment. `PUBLIC.feedback_themes` chỉ giải thích mẫu thống kê, không giả vờ đã đọc nhận xét. `HR_PRIVATE` phục vụ HR xem nội bộ, không copy, xuất chung hoặc hiển thị trong public report/history. Hai phạm vi chạy theo hai thao tác riêng; không tự gọi provider hai lần khi HR chỉ chọn một.

HR xem trước phạm vi dữ liệu gửi ra ngoài trong hộp xác nhận. Đây là xác nhận thao tác sản phẩm; API vẫn tự kiểm tra toàn bộ quyền, versions và input. Free-text redaction là best effort, không cam kết ẩn danh tuyệt đối; chỉ dùng dữ liệu hư cấu trong live smoke/demo. Giới hạn này áp dụng cả input lẫn output private.

## 3. Input và output

Input builder lấy **immutable revision** được chọn qua header hiện tại, không ghép KPI/rating live với calculation cũ. Provider chỉ thấy reference cố định `EMPLOYEE`, alias `KPI-01`… thay cho UUID/code/name/description/unit tự do. Gửi target/actual/weight/direction và điểm do server đã tính, không yêu cầu provider tính lại. Không gửi email, employee_code, tên, manager/department/position, reviewer/assignment/user IDs, request/session tokens, audit metadata hoặc secret.

Public feedback dùng cùng suppression riêng PEER/SUBORDINATE như Phase 5–6; không gửi individual ratings, số lượng của nhóm suppressed hoặc comment. Có thể gửi aggregate count/mean toàn bộ đã có trong report; residual inference giữ giới hạn đã công bố.

Private comments chỉ đọc Feedback của các assignment SUBMITTED có trong revision, không lấy submission được thêm sau lần tính. Khử email/điện thoại/URL/identifiers đã biết; normalize Unicode/control characters, không ghi raw prompt vào log/DB. Không gửi timestamp/identity/individual rating đi cùng từng comment. Thứ tự và chọn mẫu deterministic, không phụ thuộc thứ tự ORM. Tối đa 20 comments, 500 ký tự/comment, tổng 10.000 ký tự; nếu cắt/chọn mẫu phải có cờ và caveat “không bao phủ toàn bộ nhận xét”. Payload JSON tổng tối đa 64 KiB; không cắt âm thầm KPI/scores khi vượt ngưỡng, trả lỗi xử lý được. Có test nhiều dấu tiếng Việt và giới hạn byte UTF-8.

Prompt hệ thống tiếng Việt, version cố định `PROMPT_VERSION`, không nối comment thành instruction. Dữ liệu là JSON không tin cậy; yêu cầu không suy diễn thông tin thiếu, không so sánh/xếp hạng người ngoài evidence. Gemini không có tool, URL retrieval, search, code execution, function calling hoặc DB quyền. Không tin output chỉ vì provider trả JSON.

Output đúng sáu trường, không thêm identity/score/HTML:

| Trường | Giới hạn đề xuất |
| --- | --- |
| `summary` | Chuỗi không rỗng, tối đa 1.500 ký tự |
| `strengths` | 0–5 chuỗi, mỗi chuỗi 1–400 ký tự |
| `improvement_areas` | 0–5 chuỗi, mỗi chuỗi 1–400 ký tự |
| `feedback_themes` | 0–5 chuỗi, mỗi chuỗi 1–400 ký tự; tuân thủ audience |
| `recommended_actions` | 0–5 chuỗi, mỗi chuỗi 1–400 ký tự |
| `caveats` | 1–5 chuỗi, mỗi chuỗi 1–400 ký tự |

Pydantic strict, forbid extra keys, không coerce số/bool thành text, reject JSON duplicate keys/NaN, invalid control characters, rỗng/oversize/truncated/blocked response. Response text tối đa 32 KiB trước parse. Output plain text, React escape, không `dangerouslySetInnerHTML` hoặc tự render Markdown/links. Không lấy bất cứ trường AI nào ghi ngược vào KPI/score/review. Backend thêm nhãn advisory và giới hạn input từ metadata đáng tin cậy, không chỉ dựa vào caveats của model. Không tuyên bố validation schema đảm bảo tính đúng đắn nội dung.

## 4. Provider và cấu hình

Đã đối chiếu tài liệu chính thức ngày 2026-10-22: [Google Gen AI SDK](https://googleapis.github.io/python-genai/), [structured output](https://ai.google.dev/gemini-api/docs/structured-output), [model catalog](https://ai.google.dev/gemini-api/docs/models). SDK Python chính thức là `google-genai`; structured output hỗ trợ JSON Schema nhưng ứng dụng vẫn phải validate giá trị/giới hạn. Khi bắt đầu code phải kiểm tra lại API/method/model đang được hỗ trợ và pin phiên bản SDK cùng dependency graph tương thích Python 3.12/requirements.lock. Không copy model alias từ bài cũ hoặc mặc định coi preview/latest là ổn định.

Settings đề xuất: `GEMINI_ENABLED=false`, `GEMINI_API_KEY` SecretStr rỗng, `GEMINI_MODEL` rỗng; khi bật cần key/model hợp lệ. Timeout mặc định 20s, giới hạn cấu hình 5–30s; output token budget mặc định 2.048, giới hạn 512–4.096. Không cấu hình provider base URL bằng request. Chọn model text hỗ trợ structured output qua env và kiểm tra khả năng thực tế trong live smoke; không hard-code model vào nghiệp vụ. Đóng client khi shutdown.

Không có key/model hoặc tắt AI: report, scoring, health và Docker startup vẫn hoạt động; UI báo chưa cấu hình, POST không tạo attempt và không gọi mạng. Config được bật nhưng cấu hình thiếu phải fail validation an toàn. Không forward key qua `NEXT_PUBLIC_*`, web container, image build ARG hoặc image layer; chỉ migrate/API nhận đúng env cần thiết khi triển khai. Không đọc/ghi `.env` người dùng trong lượt lập kế hoạch.

Provider interface được inject để test offline. Một invocation cho một attempt, tắt retry tự động của SDK/transport; test xác nhận số request và deadline tổng, không chỉ giá trị timeout option. Không âm thầm chuyển model/provider. Mapping lỗi có code allowlist: timeout/quota/unavailable/blocked/invalid_output/configuration; không echo provider exception, response body, key hoặc prompt. HTTP timeout/quota có thể phát sinh chi phí; app không cam kết exactly-once billing khi process crash sau khi provider đã nhận request.

## 5. Lưu trữ, lease và phiên bản

Migration `20261022_0007` đã triển khai, sau `20261022_0006`, chỉ thêm `ai_analyses`, không backfill output giả. FK RESTRICT đến review và requester; composite FK `(review_id,calculation_version)` đến UNIQUE đã có của PerformanceReviewRevision ràng buộc đúng revision/cùng review. Không sửa giá trị snapshot/history.

Mỗi attempt giữ UUID, audience, generation_version tăng theo `(review_id,audience)`, calculation/evidence/engine versions, evidence_hash, input_hash, prompt/redaction/schema versions, model yêu cầu/model trả về nếu có, requested_by, client_request_id, request_fingerprint, status `RUNNING/SUCCEEDED/FAILED`, sanitized error_code, output JSON nullable, reserved/completed/generated timestamps UTC, lease_until và fencing token. Không lưu API key, raw prompt, raw provider body hoặc raw comments. Constraints kiểm tra versions/hash/enums/object JSON và status/output/timestamps nhất quán. Success row bất biến qua API; generation mới không ghi đè success cũ.

UNIQUE `(requested_by,client_request_id)` cho idempotency; request fingerprint bao review/audience/versions/regenerate intent. Cùng key khác intent trả 409. Partial UNIQUE `review_id WHERE status='RUNNING'` ngăn nhiều call cùng review, kể cả khác calculation/audience. Người đọc public chỉ thấy số thứ tự/generation của PUBLIC, không thấy số attempt/metadata private.

Lease mặc định 60s, phải lớn hơn deadline provider cộng thời gian hoàn tất. Lần ghi tiếp theo có quyền sẽ đánh dấu RUNNING quá hạn thành FAILED với code `generation_expired` rồi mới reserve; GET không recovery/ghi. Completion kiểm tra chính xác attempt/token/status/deadline, không overwrite attempt đã thất bại hoặc lease mới. Cooldown tối thiểu 30s giữa các reservation của cùng review, kiểm tra dưới khóa; caller retry cùng idempotency key không tạo reservation/call mới. Không thêm queue hoặc giữ DB connection trong lúc gọi provider.

## 6. Ba bước giao dịch

1. **Reserve:** exact Origin/CSRF, HR/account/family revalidation; scoped discovery, guard → sorted ADMIN/users → family → cycle → participant → review → attempt. Chỉ CURRENT hoặc FINALIZED; version/evidence/hash phải nhất quán, lấy revision đúng. ACTIVE hoặc CLOSED đã có current finalized report đều được tư vấn. Không gọi `writable()` của KPI để chặn nhầm finalized/CLOSED. Reused success nếu cùng calculation/audience và không yêu cầu regenerate; nếu có success current, regenerate bắt buộc xác nhận và expected latest generation. Ghi reservation + audit atomically; commit xong mới gọi provider.
2. **Provider:** giải phóng mọi transaction/row/advisory locks, đóng trả connection về pool; gọi với input immutable và deadline. Không dùng Session đang mở/ORM object lazy load. Scoring/KPI/auth/close vẫn phục vụ bình thường khi Gemini chậm.
3. **Complete:** transaction ngắn, cùng lock order. Revalidate HR/account/family, scope, versions/hash, model/prompt intent và fence. Recalculation/evidence thay đổi thì đánh dấu attempt FAILED `analysis_stale`, không gắn output vào revision mới và không trả nó như current. Role/account/logout thay đổi thì loại output, không trả nội dung cho caller mất quyền. Nếu chỉ finalize/close nhưng evidence/calculation không đổi, cho hoàn tất; AI không tăng cycle/evidence/calculation version. Success + audit cùng commit; lỗi ghi DB/audit không phá numeric/history cũ, RUNNING còn lại được lease recovery ở lần ghi sau.

Không được rollback reservation rồi gọi lại provider bằng version mới một cách tự động. Failed regeneration giữ last successful analysis, cả lịch sử revision cũ. Stale được suy ra lúc đọc theo calculation/evidence hash, không sửa mọi KPI/feedback writer để invalidate AI rows. Kết quả finalized lịch sử không tự vô hiệu chỉ vì deploy engine/prompt/model mới; hiện rõ nguồn/version đã dùng.

## 7. API đề xuất

| Endpoint `/api/v1` | Quyền và hợp đồng |
| --- | --- |
| GET `/performance/{review_id}/ai-analysis?audience=PUBLIC` | Scoped saved state; GET không gọi provider/ghi audit. HR_PRIVATE chỉ HR, trả 403 trước đọc/serialize private rows |
| POST `/performance/{review_id}/ai-analysis` | HR; `{client_request_id,expected_calculation_version,expected_evidence_version,audience,regenerate,expected_latest_generation?}` strict/forbid extra. Regenerate=true cần expected_latest_generation; no success trong audience yêu cầu giá trị 0 cho confirmation |
| GET `/reviews/{review_id}/ai-analyses?audience=PUBLIC&page=1&page_size=20` | Scoped immutable history, tối đa 100/trang; filter audience trong SQL trước count/pagination; HR_PRIVATE chỉ HR |
| GET `/reviews/{review_id}/ai-analyses/{analysis_id}` | Scoped detail, kiểm tra audience của row trước serialize; không cho UUID của private bypass role |

Phân biệt review UUID với employee UUID của API tính điểm. Response no-store; thiếu report/ngoài live scope cùng 404. Public DTO không requester ID, lease token, input hash, private attempt status/count hoặc provider diagnostic. HR nhận metadata xử lý qua DTO riêng, không raw prompt.

POST 201 tạo và hoàn tất generation mới; 200 reused success; replay RUNNING trả 202 metadata attempt hiện có; replay terminal trả 200 representation với status SUCCEEDED/FAILED và output hoặc error_code tương ứng, không gọi lại. Sau reload UI đọc attempt bằng detail và HR tạo request_id mới khi chủ động retry. Lỗi 409 `review_stale`, `stale_calculation_version`, `stale_evidence_version`, `stale_analysis_version`, `generation_in_progress`, `analysis_stale`, `idempotency_conflict`; 429 `generation_cooldown`; 503 `ai_not_configured`/provider unavailable/quota mapping allowlist; 504 timeout; 502 invalid/blocked provider output; 401/403 auth như hiện có. Error envelope có request_id, không chứa nội dung provider.

`expected_latest_generation` là generation_version của success hiện tại trong đúng audience/calculation, hoặc 0 nếu chưa có success ở calculation đó. GET suy ra attempt quá lease thành trạng thái hiển thị quá hạn/can_retry, không sửa row; authorized POST sau đó mới recovery. Không để UI quay vô hạn vì một RUNNING đã hết lease.

Read state `NOT_GENERATED/RUNNING/CURRENT/STALE/FAILED`, có `current_analysis` nullable, `last_successful_analysis` gắn nhãn phiên bản cũ, `latest_attempt` đúng audience và capabilities. Failed regen không đổi CURRENT thành không có kết quả nếu còn success current. Reuse đọc cache không cần key còn được cấu hình; thiếu key chỉ ngăn gọi mới. Audit `ai_analysis.requested/succeeded/failed/expired` chỉ IDs/versions/audience/model/prompt/error code cần thiết, không output/ratings/comments/secret.

## 8. UI/UX và nghiệm thu

Gắn section “Tư vấn AI” vào trang kết quả Phase 6, dưới điểm chính; giữ header nhóm, sidebar theo role và tabs employee/cycle hiện có. Không thêm một dashboard hay picker nhân viên/kỳ trùng. PUBLIC hiển thị advisory, model/time/calculation, current/stale rõ. HR_PRIVATE nằm trong khối chỉ HR có nhãn “Nội bộ HR”, không đổi public tab mặc định và không prefetch private cho role khác.

HR chọn tạo public hoặc phân tích nhận xét nội bộ, xem hộp xác nhận phạm vi gửi, rồi mới POST. Không tự generate khi mở trang, refetch, vào lịch sử, nhấn tính điểm hoặc chốt kỳ. Regenerate xác nhận tạo bản mới, giữ bản trước nếu lỗi; capture expected versions/latest generation ở lúc mở confirmation, reset xác nhận khi context đổi. Pending không cho double-click; nếu mất response giữ client_request_id để tra cứu/replay, không tự tạo key mới. Không dùng retry mutation mặc định.

Employee/manager chỉ đọc PUBLIC; ADMIN không fetch report; nhận xét private không lọt DOM/cache/query request. Query keys có user/review/audience/generation; auth clear, KPI/feedback/calculate invalidate current AI, history vẫn immutable. Test input/output malicious HTML, prompt injection, small groups, public/private SQL scope, stale provider completion, revoke khi chờ, lease expiry/late response, rollback, cooldown/idempotency và bounded query count.

CI mặc định không cần key và không gọi Google. Tests sử dụng adapter giả; Docker smoke keyless vẫn chứng minh numeric workflow không phụ thuộc AI, dữ liệu AI mock được tạo ở test môi trường có nhãn rõ và không deploy fake provider vào production. Live Gemini smoke chỉ chạy opt-in với key/model người vận hành tự cấu hình, dữ liệu hư cấu và hành động tạo rõ ràng; ghi riêng nếu chưa chạy, không giả vờ đã nghiệm thu live.
