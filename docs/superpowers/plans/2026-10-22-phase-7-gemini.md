# Kế hoạch Phase 7 — Gemini và tư vấn hiệu suất

Ngày: 2026-10-22. Trạng thái: **đã triển khai, đang nghiệm thu offline; Gemini thật chưa được gọi**. Baseline của lượt triển khai: 767 backend và 104 web test đạt; các gate cuối được ghi riêng bên dưới khi hoàn tất.

Tham chiếu: [hợp đồng đề xuất](../../phase-7-contract.md), [AI design](../../ai-design.md), [kiến trúc](../../architecture.md), [nghiệm thu Phase 6](2026-10-22-phase-6-performance.md), [review](../../phase-6-review.md), [API](../../api.md), [vận hành](../../deployment.md).

## Đối chiếu trước lập kế hoạch

- [x] HEAD `8bf384b`, working tree clean và main đồng bộ origin/main; không có plan/module/migration Phase 7 khác.
- [x] Đọc scoring/report/revision models, service/read scope, input snapshots, auth/CSRF/write locks, Settings/dependencies, report UI, Compose/env và CI.
- [x] Có evidence/calculation hashes, immutable revision membership, live SQL scope và trang kết quả để nối AI; không cần viết lại scoring hoặc dựng trang chọn ngữ cảnh mới.
- [x] Phase 6 runtime `f595f23` có [CI 39715137000](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/39715137000) 767 backend/104 web test; là evidence trước đó, không coi là chạy lại trong lượt này.
- [x] Đối chiếu tài liệu chính thức Google: SDK `google-genai`, structured JSON/Pydantic, model catalog; chưa chốt version package/model alias hoặc cài dependency. Kiểm tra lại khi code.
- [x] Đề xuất hai audience: PUBLIC dùng số/aggregate không comment; HR_PRIVATE phân tích nhận xét đã khử định danh. Không dùng output có nguồn private cho employee/manager.

Lượt lập kế hoạch ban đầu chỉ sửa tài liệu. Lượt triển khai được người dùng duyệt sau đó bổ sung SDK/schema/API/UI và kiểm thử theo các task bên dưới. Không đọc key trong `.env` hoặc gọi Gemini thật. Nghiệm thu dùng project Docker/ports/volume riêng; không tích lũy image tag theo từng task, dọn image nghiệm thu không dùng sau gate, giữ nguyên dữ liệu/volume người dùng.

## Luồng bàn giao dự kiến

HR mở kết quả CURRENT/FINALIZED → chọn tư vấn public hoặc nhận xét nội bộ → kiểm tra phạm vi dữ liệu và xác nhận → reserve/commit → gọi Gemini ngoài DB transaction → validate/revalidate/commit → xem tư vấn đúng phiên bản. Employee/current manager chỉ xem public đã lưu. Nếu sửa evidence/tính lại trong khi AI đang chạy, output không được gắn sang kết quả mới. Provider lỗi hoặc thiếu key không ảnh hưởng tính điểm, chốt hoặc đóng kỳ. Tạo lại phải chủ động và giữ success cũ khi lỗi.

## Task 1 — Baseline, provider decision và cấu hình optional

File dự kiến: `apps/api/app/core/config.py`, `pyproject.toml`, `requirements.lock`, `.env.example`, Compose/API wiring, tests settings/provider contracts.

- [ ] Chạy full PostgreSQL baseline `_test` và web; ghi head/môi trường/kết quả thực, không dùng số 767/104 làm fixed assertion.
- [ ] Xác minh model text/structured output, SDK API, timeout/retry units và dependency compatibility từ tài liệu chính thức. Pin SDK/graph thực dùng; không hard-code model hoặc dùng SDK legacy từ bài cũ.
- [ ] `GEMINI_ENABLED=false`, SecretStr key và model optional khi tắt; khi bật validate cấu hình, timeout 5–30s/output budget 512–4096, secrets không có trong errors/repr/browser/image.
- [ ] Adapter interface inject được, chỉ tạo client khi cần, close lifecycle đúng; không lookup model/call provider lúc startup/GET/health. Kiểm tra tắt/keyless vẫn chạy mọi chức năng hiện tại.
- [ ] Kiểm tra image runtime không có prompt/key/test tooling; chỉ API runtime được nhận key, không thêm service/queue hoặc frontend SDK.

Gate: config/provider-boundary tests, Ruff/mypy và dependency lock reproducible; chưa cần live credential. Commit `feat(ai): add optional Gemini configuration and provider boundary`.

## Task 2 — Input minimization, prompt và output schema

File dự kiến: `app/modules/ai/{input_builder,redaction,prompts,schemas,provider}.py`, unit tests.

- [ ] Viết test input/output trước implementation: public không comment/identity/raw snapshot/individual rating/suppressed count; private chỉ đọc submitted membership của đúng revision.
- [ ] Alias employee/KPI, bỏ tên/code/unit tự do/graph; immutable numerical input, frozen scores/policy và filtered aggregate. Không đưa PII trong KPI labels vào prompt.
- [ ] Private redaction và deterministic sampling/truncation theo contract; UTF-8/Unicode/URL/email/phone/known identifiers, payload 64 KiB, comments 20×500/tổng 10.000 ký tự; thông báo sampling bằng metadata/caveat.
- [ ] Prompt tiếng Việt versioned, dữ liệu bất tín nhiệm không thành instruction; không tools/search/function calling. PUBLIC không được bịa nội dung nhận xét chưa gửi.
- [ ] Sáu trường strict, extra/type/duplicate JSON key/NaN/control/length/array validation; response <=32 KiB, reject provider blocked/truncated output. Schema provider chỉ hỗ trợ subset; server validation độc lập.
- [ ] Kiểm tra số call thực, timeout tổng và tắt SDK retries; mapping lỗi sanitized. Không logs/full prompt/raw body/secret. Oracle tests cho input hash không phụ thuộc query order.

Gate: input/output/privacy/adversarial/provider mocks qua, numeric engine không đổi. Commit `feat(ai): build bounded audience-safe Gemini payloads`.

## Task 3 — AIAnalysis schema, lease và idempotency

File dự kiến: `ai/{models,repository}.py`, `app/models.py`, migration `20261022_0007`, integration cleanup/schema tests.

- [ ] Test RUNNING/SUCCEEDED/FAILED CHECKs, nullable output/timestamps đúng trạng thái, versions/hash/JSON, FK review/revision/requester RESTRICT và cùng review/revision mapping.
- [ ] Per-audience generation sequence, append attempts/history; UNIQUE requester/client_request_id + request fingerprint; partial UNIQUE review RUNNING, chống song song cả khác audience/version.
- [ ] Lease deadline/fencing, cooldown 30s và recovery chỉ trên authorized write. Late completion không đổi expired/failed attempt; process crash không giữ chặn vĩnh viễn.
- [ ] Không lưu raw comments/prompts/provider body/key; output private luôn có audience được constrain. Public pagination/count không nhìn thấy private rows/counter/requester.
- [ ] Sole head/metadata parity/clean install/downgrade-upgrade giữ Phase 6 scores/revisions/finalization/cycles và feedback; không backfill AI giả.

Gate: PostgreSQL constraints/migration tests và model lint/types qua. Commit `feat(ai): persist versioned attempts with fenced generation leases`.

## Task 4 — Reserve, provider call và completion

File dự kiến: `ai/{service,router,authorization}.py`, audit allowlist, app wiring; transactional/provider integration tests.

- [ ] HR exact Origin/CSRF, locked account/role/family revalidation; live scope và CURRENT/FINALIZED version check. CLOSED finalized được phân tích, không dùng KPI writable guard chặn nhầm.
- [ ] Reserve + audit transaction; reused current success không gọi provider; regenerate phải có expected latest generation; không tự replace success do đổi config.
- [ ] Repeated request_id cùng intent không tạo call; intent khác 409; RUNNING replay 202 có thể tra cứu, terminal replay an toàn. Cooldown/lease rejection trước provider call.
- [ ] Commit/release connection trước gọi mạng; chứng minh scoring/auth/KPI/close request khác không bị giữ guard/row locks/pool bởi provider chậm.
- [ ] Completion revalidate quyền/session/evidence/calculation/hash và fence; stale/revoked output không persist success/không trả body cho người mất quyền. Finalize/close không đổi evidence thì completion được phép.
- [ ] Audit/DB errors ở cả reserve/complete rollback đúng phần transaction; lease recover khi cần; không tăng numeric versions hoặc sửa revisions. Failure giữ last success và không retry nền.

Gate: expected codes, reuse/idempotency, provider errors và rollback tests qua. Commit `feat(ai): generate advisory analyses outside database locks`.

## Task 5 — Scoped reads, history và stale presentation

File dự kiến: `ai/{presenters,repository,schemas}.py`, API docs và privacy/read-consistency tests.

- [ ] GET không call provider/ghi audit/recover lease. Current vs last successful vs latest attempt được tách, không xóa success khi regen lỗi.
- [ ] PUBLIC/HR_PRIVATE scope trước count/filter/pagination/detail; guessed private UUID, audience query, ADMIN hoặc old manager không bypass. Own reviewer không có report scope.
- [ ] Report/revision/analysis dùng live SQL scope nhất quán; transfer/unlink/role cập nhật quyền, không cập nhật lịch sử AI. DTO public không private counters/status/metadata/lease/token/input hash.
- [ ] STALE theo calculation/evidence hash; current_result AI=null nếu lỗi nguồn; finalized history dùng engine đã chốt, không invalid chỉ vì ứng dụng đổi model/prompt.
- [ ] REPEATABLE READ hoặc tương đương cho aggregate, tie-breakers/pagination và bounded query counts; AI reads không biến thành N+1 trên report/history.

Gate: privacy/current/stale/history/reader-vs-writer tests qua. Commit `feat(ai): expose scoped advisory state and immutable history`.

## Task 6 — UI tiếng Việt trên trang kết quả hiện có

File dự kiến: `apps/web/src/features/ai/`, nối `features/performance/report.tsx`, API types và cache invalidation chung.

- [ ] Thêm section “Tư vấn AI” sau điểm, giữ header/tab nhóm + sidebar theo role, context employee/cycle và bố cục hiện có. Không thêm trang chọn ngữ cảnh/dashboard trống.
- [ ] PUBLIC đọc được cho employee/manager, HR_PRIVATE khối “Nội bộ HR” chỉ HR; không prefetch private/DOM hidden chứa private content cho role khác.
- [ ] Advisory/model/time/calculation, chưa tạo/đang chạy/current/stale/lỗi/chưa cấu hình rõ; hiển thị số điểm server không AI chỉnh. History gắn nhãn và phạm vi, không dùng private output cho public view.
- [ ] Hai thao tác tạo tách biệt; xác nhận dữ liệu gửi, captured versions/latest generation và request_id. Không POST khi GET/refetch/open page/calculate/finalize. Regenerate riêng, không silent retry/double click.
- [ ] Response bị mất: giữ intent/request_id, tra cứu/replay cùng key; retry chủ động mới dùng key mới. 409/cooldown/provider lỗi giữ success và hướng xử lý; reset confirmation khi context đổi.
- [ ] Query keys user/review/audience/generation; auth clear; KPI/feedback/calculate invalidate current; immutable history không mất. Không Markdown HTML injection hoặc link provider tự tạo.
- [ ] Behavior tests mọi role/state, no unauthorized fetch, refetch không phát sinh chi phí, pending, conflict/background change, timeout/retry, private cache separation. Edge 390/1280px/keyboard trên report và các màn cũ.

Gate: web tests/lint/types/build/browser qua, không cài thư viện UI mới nếu không cần. Commit `feat(web): add explicit audience-aware AI advisory workflows`.

## Task 7 — Review xuyên module và concurrency

File dự kiến: real-account E2E, `test_ai_{security,concurrency,privacy}.py`, `docs/phase-7-review.md`.

- [ ] Bootstrap/login/create/link thật → scoring → generate public/private bằng injected provider → old version/stale/recalc → regenerate fail giữ success → finalize/close → saved reads/history/live scope.
- [ ] Barrier/Event: hai generate cùng review kể cả khác version/audience; lease expire/reserve/late completion; cooldown/request replay; regenerate + different idempotency intent.
- [ ] Provider chậm đua KPI/feedback/recalculate, finalize/close, account disable/logout/role/manager transfer. Giữ lock order Phase 4–6, không locks qua mạng, deadlock/pool timeout được bắt.
- [ ] Không echo PII/small groups/comments private qua output/public/errors/audit/logs/cache; prompt injection/schema valid nhưng nội dung vô căn cứ có caveat, không quyền sửa điểm.
- [ ] Audit/DB/transport failure từng ranh giới, giữ old success, không nhận output sau fence/expiry; kiểm kê mọi GET không gọi mạng.
- [ ] Lặp các race quan trọng ít nhất năm lượt trên DB `_test` riêng, không chạy integration đồng thời trên cùng DB; ghi số thực chạy từng lượt. Review trực tiếp hay độc lập phải ghi đúng cách thực hiện.

Gate: không còn blocker về disclosure/cost duplication/stale attachment/authorization/deadlock/data loss. Commit `test(ai): verify provider isolation privacy and concurrent generation`.

## Task 8 — Docker/CI, live opt-in và bàn giao

File dự kiến: CI/smoke scripts, README Việt/Anh, API/database/deployment/architecture/AI design và contract/plan.

- [ ] Full PostgreSQL backend, Ruff/mypy và toàn bộ web tests/lint/types/build, ghi số thực/head đúng. Mặc định không cần key/internet Google và không có flaky live calls trong CI.
- [ ] Fresh isolated Docker project với keyless startup, health/scoring/finalize/close vẫn qua; không hard-code test provider trong production. Provider transport mock chỉ tồn tại trong test, không đóng gói vào runtime.
- [ ] PostgreSQL acceptance fixture có AI success/failure/private/public/lease/history, rồi restart riêng PostgreSQL và so nội dung trước migration rerun. Seed fixture bằng test runner/provider inject ở môi trường test riêng, không thêm fake-provider switch/endpoint vào production. Nếu Docker keyless không có AI rows thì ghi rõ, không tuyên bố đã chứng minh AI-content persistence chỉ bằng count=0.
- [ ] Upgrade từ head 0006 giữ numeric results/revisions/finalized timestamps và feedback. Runtime UID/nonroot/no .env/no secrets, dependency install reproducible, no fake analysis backfill.
- [ ] Live smoke opt-in: operator tự cấu hình key/model và chủ động tạo trên dữ liệu hư cấu; xác minh model/timeout/schema thực dùng, không log key/prompt. Nếu chưa có key thì đánh dấu **chưa nghiệm thu live**, vẫn báo rõ gate offline đã đạt.
- [ ] Dùng tối đa image tags nghiệm thu cần thiết, dừng stack và dọn images không còn dùng sau check; không xóa volume đang dùng hoặc chạy blanket prune. Không tạo container theo từng test/task.
- [ ] Cập nhật tài liệu dữ liệu ra ngoài, hai audience, giới hạn redaction/advisory, model/key/timeout, retry/lease/recovery/cooldown, historical current/stale và chi phí không exactly-once khi crash.
- [ ] CI backend/frontend/docker-smoke thành công đúng runtime commit; record URL, local/browser/race/live-or-not evidence; docs links/UTF-8, git clean, commit/push theo ủy quyền. Chỉ đánh dấu Phase 7 hoàn tất theo các gate được ghi rõ, không mạo nhận live smoke nếu chưa chạy.

Gate: release vẫn dùng được khi Gemini tắt/lỗi; chỉ lên dashboard Phase 8 sau nghiệm thu. Commit `docs: complete Phase 7 acceptance and Gemini operations`.

## Bằng chứng của lượt lập kế hoạch

Chỉ đối chiếu code và tài liệu, không cài SDK, sửa env, migration, mở provider client, chạy full tests hoặc Docker. Các checklist implementation giữ `[ ]`. Cơ sở Phase 6 là evidence CI đã ghi nhận, không bảo đảm bằng suy đoán rằng mọi lần build sau đều thành công. Kiểm tra tài liệu lần này cần xác nhận link nội bộ/UTF-8, tám task và sole head vẫn `20261022_0006`. Hai-audience là đề xuất chi tiết mới được nêu rõ trong contract để review trước triển khai.

Kiểm tra thực tế lượt lập kế hoạch: UTF-8/link file nội bộ hợp lệ, đủ tám task, tất cả implementation gates chưa đánh dấu; `alembic heads` trả duy nhất `20261022_0006`. Chỉ README và tài liệu thay đổi; không có app/dependency/env/schema/runtime diff.
