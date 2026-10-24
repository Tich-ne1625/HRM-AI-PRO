# Kế hoạch Phase 9 — Bảo mật và tích hợp

Ngày lập: **24/10/2026**. Trạng thái: **hoàn thành 8/8 task**, runtime `9821e82`; xem [báo cáo nghiệm thu](../../phase-9-report.vi.md), [full CI](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40109252558) và [browser/persistence CI](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40109315010). Kế thừa Phase 8 runtime `88700d8`, docs `758e93a`, [CI baseline](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40086271058): 830 backend/133 web tests. Không coi đây là số test nghiệm thu Phase 9.

Đọc [hợp đồng Phase 9](../../phase-9-contract.md), [báo cáo Phase 8](../../phase-8-report.vi.md), [kiến trúc](../../architecture.md) trước khi code. Làm tuần tự các task có phụ thuộc; không giao nhiều tiến trình integration cùng sử dụng một database `_test`.

## Task 1 — Kiểm kê và ma trận bảo mật

**Đầu ra:** `docs/phase-9-security-matrix.md` và finding ledger trong tài liệu đó; danh sách chính xác allowlist audit, các invariant và đường đi cần bổ sung test.

- Đối chiếu mọi route trong `app/main.py` và các router với role, resource scope, CSRF/Origin, loại UUID, response projection, cache và audit. Kiểm tra list/count/detail/history/dashboard đồng nhất.
- Tham chiếu test có sẵn thay vì viết lại: `test_auth_*`, `test_review_security`, `test_feedback_security/confidentiality`, `test_performance_security/privacy/concurrency`, `test_ai_workflows`, `test_ai_reports`, `test_dashboard`.
- Rà frontend auth/API client/query keys/error rendering và proxy/header config; ghi đường đi nghi ngờ, không gọi là lỗ hổng nếu chưa có tái hiện.
- Mỗi finding có ID, mức ảnh hưởng, file/đường đi, cách tái hiện bằng dữ liệu test, fix dự kiến, regression test, trạng thái. Lỗi lộ quyền/secret hoặc ghi sai dữ liệu chặn nghiệm thu; lỗi còn lại có lý do và giới hạn cụ thể, không ghi “pass” thay vì xử lý.
- Đóng băng enum action/entity audit từ service thực tế, không suy đoán tên event. Chốt ngưỡng/config throttling và body limit theo hợp đồng; nếu phát hiện xung đột, cập nhật hợp đồng bằng lý do trước khi thay code.

**Gate:** bảng phủ mọi router; test hiện có/thêm mới được phân biệt; danh sách migration/API/config tác động review được. Chưa chạy thao tác ghi vào local demo.

## Task 2 — Quyền, phiên và cache trên toàn ứng dụng

**Phụ thuộc:** Task 1. **Tệp trọng tâm:** `core/policies.py`, `core/domain_writes.py`, các scope repository; web `lib/api-client.ts`, `features/auth/*`, query client và các trang dữ liệu cá nhân.

- Bổ sung test UUID chéo người/role, unlinked/inactive, DRAFT/CLOSED, chuyển quản lý và reviewer lịch sử. Bao gồm count/trang, hoạt động và tư vấn riêng; không sửa quyền nghiệp vụ để test dễ qua.
- Tái hiện request chậm về sau logout/đổi tài khoản/role, refresh 401 đồng thời, mutation nhận 401 và mất response. Dùng request/auth epoch hoặc hủy request nếu cần; khóa API client vào same-origin, không replay AI hoặc thao tác của phiên trước.
- Kiểm tra khi authority mất: không chỉ ẩn menu; DOM/form/query cache không phục hồi nội dung cũ sau refetch lỗi hoặc back navigation. Auth errors và network errors có xử lý rõ; không tự logout người dùng chỉ vì mạng chập chờn.

**Gate:** regression backend/web cho finding; user A không thấy response/cache của B; late refresh không hồi sinh quyền bị thu hồi. GET đã bắt đầu theo snapshot có semantics được mô tả, không hứa thu hồi dữ liệu đã tải.

## Task 3 — Boundary HTTP và giới hạn request/đăng nhập

**Phụ thuộc:** Task 2. **Tệp trọng tâm:** config/errors/main/auth, Next.js config, migration/model limiter riêng, `.env.example`, deployment docs.

- Thêm body limit 128 KiB thực sự đọc theo byte cho API JSON; 413/error/cache đúng; thử thiếu/sai Content-Length và chunked qua proxy, không buffer vô hạn.
- Login limiter PostgreSQL theo HMAC email chuẩn hóa: 10 lượt/300 giây mặc định, reserve trước verify password, upsert/window dùng DB time; concurrent workers chỉ chia sẻ một hạn mức. Generic 429/Retry-After cho email có/không tồn tại; lỗi storage 503, không fail-open.
- Thêm migration kế tiếp từ head `20261022_0007` cho `auth_login_limits`; không backfill evidence/AI. Thêm CLI cleanup TTL có giới hạn và validate config; không background cleanup ngầm, không tin forwarded IP tùy ý.
- Đối chiếu mọi assertion migration head trong tests, smoke và `scripts/check_performance_persistence.py`; cập nhật head kỳ vọng nhưng vẫn so sánh đầy đủ dữ liệu cũ. Không làm mất coverage nâng cấp/downgrade Phase 7 khi có migration mới.
- Thêm security headers tương thích production/hydration, no-store cả lỗi cá nhân; HTTPS-only HSTS, local HTTP vẫn chạy. Giữ strict Origin/CSRF và cookie behavior.
- Kiểm tra lỗi/log không chứa password/token/key/request body. Rate-limit test dùng ngưỡng nhỏ/config riêng, không chờ 5 phút thật; kiểm tra hết cửa sổ bằng clock/DB time được điều khiển trong fixture.

**Gate:** Postgres concurrency limiter, 413 chunked, secret canary, cookie/proxy/security-header tests; image startup keyless/production config validation; migration roundtrip giữ dữ liệu cũ. Lưu ý giới hạn per-email không chống được DDoS và có tradeoff tạm chờ tài khoản.

## Task 4 — Tính nguyên tử và cạnh tranh xuyên module

**Phụ thuộc:** Task 2–3. **Tệp trọng tâm:** test integration hiện có và các regression theo finding; chỉ sửa service có lỗi tái hiện.

- Giữ order guard → account/family → cycle/participant/review theo code đã kiểm chứng; audit và domain commit cùng nhau.
- Race sửa tổ chức/thu hồi quyền với writer đang chờ; KPI/feedback với calculate/finalize; close với activate; provider completion với revoke/recalculate/finalize; refresh/logout. Tái sử dụng case đã có, chỉ mở rộng cặp chưa phủ.
- Inject lỗi flush/audit/commit tại ranh giới thực, khẳng định dữ liệu/version/revision/audit không nửa vời. Không giữ connection/lock khi provider chờ.
- Chạy nhóm race trọng yếu 5 lượt liên tiếp trong một DB disposable, tuần tự. Ghi số case thực thu thập và từng lượt; barrier/event + timeout, không che lỗi bằng retry toàn test.

**Gate:** không treo/5xx ngoài fixture dự kiến; invariant và rollback assertions đạt, ledger có bằng chứng. Không đổi semantics replay/finalization để giải quyết race bằng cách bỏ qua kiểm tra.

## Task 5 — AI isolation và lỗi tích hợp

**Phụ thuộc:** Task 4. **Tệp trọng tâm:** AI provider/input/service/reports, SDK transport và web AI controls/tests.

- PUBLIC không lẫn private comment/identity, kể cả sau nhiều lần tạo và đổi scope; HR_PRIVATE detail/list/count chỉ HR. Nội dung AI là text, không HTML executable hoặc nguồn thay đổi điểm.
- Kiểm tra malformed/truncated/schema-invalid output, quota/404/timeout, stale evidence, lease expiry, late fence và lost response; giữ success cũ, kiểm tra số lượt gọi provider.
- Numeric scoring/finalize/close/dashboard và saved reads vẫn hoạt động khi AI tắt hoặc provider lỗi. Kiểm tra GET không init client/gọi provider/ghi audit/hồi phục lease.
- Hoàn thiện lỗi/xác nhận trên UI nếu finding yêu cầu. Test fake/provider override chỉ trong harness; không thêm cờ fake runtime và không gọi Gemini thật ở CI.

**Gate:** offline SDK + integration + UI assertions; không có secret trong logs/build artifacts. Live HR_PRIVATE/qualitative advice vẫn là kiểm tra riêng nếu sau này được yêu cầu, không chặn hoặc giả mạo bằng chứng offline.

## Task 6 — API đọc audit đã có trong kiến trúc

**Phụ thuộc:** Task 1 đóng băng allowlist, Task 3 HTTP guards. **Tệp dự kiến:** `modules/audit/{router,schemas,repository/service}.py`, `main.py`, integration tests, `docs/api.md`.

- Thêm GET `/api/v1/audit-logs` theo hợp đồng; ADMIN events hệ thống/tài khoản, HR events HR-domain đã cho phép; không events AI/auth/password.
- DTO projection tối thiểu, không serialize raw AuditLog ORM/metadata. Áp dụng role/action/entity trước count; sort ổn định và snapshot cho total/page.
- Test 401/403, action ngoài scope/không tồn tại, invalid page, metadata/actor/secret sentinels, stable pagination và GET không ghi. Chỉ thêm index nếu có bằng chứng từ Task 8.

**Gate:** API contract đạt; không đổi quyền activity dashboard hiện có; không mở rộng thành trang audit/export hoặc endpoint sửa/xóa.

## Task 7 — E2E có ghi dữ liệu trên stack thử nghiệm riêng

**Phụ thuộc:** Task 2–6. **Tệp trọng tâm:** `scripts/smoke_auth.py`, checker persistence, test browser/harness mới và CI workflow.

- Project/cổng/volume test riêng, guard trước cleanup; seed fictional data/password tạm qua stdin. Tuyệt đối không dùng `insighthr` demo người dùng hoặc volume của nó để chạy flow ghi/reset.
- Trình duyệt thực hiện submit form qua chuỗi ADMIN → HR → reviewer → manager → HR chốt/đóng. Thử lỗi 409/stale, khóa/revoke quyền, role switch, numeric reports/dashboard và saved AI detail/list.
- Xác nhận tạo AI trong harness provider giả cô lập hoặc transport mock; runtime production vẫn Gemini tắt. Không dùng lời gọi thật để “làm xanh” CI và không chỉ đọc fixture rồi coi như đã test nút tạo AI.
- Chạy clean install và upgrade từ dữ liệu trước Phase 9; fingerprint rõ bảng/field được kiểm tra, đọc sau PostgreSQL-only restart trước khi migration chạy lại. Giữ nguyên revisions/AI/cycle snapshots; không nhầm startup empty DB với nghiệm thu nâng cấp.
- Lưu báo cáo máy đọc được và artifacts đã làm sạch vào CI; phân biệt test unit/integration, API proxy smoke và UI interactions. Thêm browser dependency chỉ ở test tooling, không image runtime.

**Gate:** full workflow/deny/error paths qua trình duyệt, Docker persistence và upgrade đạt. Ảnh chụp đẹp hoặc số test cũ không thay cho kết quả thao tác thực.

## Task 8 — Baseline hiệu năng, tổng nghiệm thu và báo cáo

**Phụ thuộc:** Task 7 và các task trước. **Tệp dự kiến:** script benchmark/fixture test, workflow manual nếu cần, `docs/phase-9-report.vi.md`, deployment/API/README.

- Dataset/load theo hợp đồng: 1.000 hồ sơ/20 phòng ban/2 chu kỳ, counts thực ghi trong report; không Argon2 cho mỗi request đo GET và không gọi Gemini. Tách warm-up, đăng nhập và giai đoạn đo.
- Đo dashboard/AI list/audit list, ít/nhiều scope, page đầu/sau; 5 client × 60 giây. Ghi p50/p95/max, SQL count, lỗi, máy/commit/cấu hình; kiểm tra plan trước khi đề xuất index. Không đặt SLA giả hoặc gate thời gian phụ thuộc runner chia sẻ.
- Full pytest PostgreSQL, Ruff/mypy; web tests/lint/typecheck/build; Compose/E2E/upgrade; nhóm race 5 lượt. Lưu chính xác commit/CI link, số test thực, finding được sửa/còn chấp nhận và cách chạy lại.
- Rà trực tiếp thay đổi theo threat matrix; không ghi “review độc lập” nếu không có reviewer độc lập. Tài liệu secrets/config/limiter TTL/header/audit/limitation được cập nhật. Chỉ mark Phase 9 hoàn tất khi mọi gate có bằng chứng.

**Gate bàn giao:** runtime/CI có thể đối chiếu, bộ demo người dùng giữ nguyên, báo cáo tiếng Việt hoàn chỉnh. Sau đó mới chuẩn bị Phase 10 Kubernetes/docs; không triển khai production ngoài phạm vi.

## Cách kiểm tra khi triển khai

Tại `apps/api`, dùng virtualenv Python 3.12 và `TEST_DATABASE_URL` chỉ tới DB có tên kết thúc `_test`. Lệnh `python -m pytest -q`, `ruff check app tests alembic`, `mypy app`; tại `apps/web` chạy `npm test -- --run`, `npm run lint`, `npm run typecheck`, `npm run build`. Chạy các bộ integration/race tuần tự. Lệnh/harness E2E, limiter cleanup và benchmark sẽ được ghi cụ thể khi tạo, không giả định script chưa tồn tại.

Trong lượt lập kế hoạch này chỉ thay tài liệu; chưa chạy lại test runtime, load test, migration hoặc cập nhật Docker, chưa thay `.env` và chưa gọi Gemini.
