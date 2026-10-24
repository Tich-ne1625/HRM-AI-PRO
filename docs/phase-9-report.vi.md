# Báo cáo Phase 9 — Bảo mật và tích hợp

Ngày nghiệm thu: **24/10/2026**. Runtime: **`9821e82`**, gồm phần bảo mật `d5e7b21` và bộ nghiệm thu/refresh error handling `9821e82`. Đã hoàn thành 8 task theo [hợp đồng](phase-9-contract.md) và [kế hoạch](superpowers/plans/2026-10-24-phase-9-security-integration.md).

## Kết quả có thể đối chiếu

| Gate | Kết quả |
| --- | --- |
| [Full CI tại runtime cuối](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40109252558) | **843 backend tests**, Ruff sạch, mypy **103 source files**; **140 web tests / 21 files**, lint/typecheck/build; Docker smoke/persistence đều đạt |
| [CI nghiệm thu riêng](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40109315010) | Chrome **155.0.8059.39**, 4 role, **32 lần gửi từ UI**, 18 ảnh ở 1280/390 px; không runtime exception hoặc tràn ngang trang |
| Races/faults | **5/5 lượt, mỗi lượt 145 test đạt**, chạy tuần tự cùng DB `_test`; không retry toàn suite để che lỗi |
| HTTP thật qua proxy | Body **131.073 byte** với Content-Length và chunked đều 413/no-store/nosniff |
| Migration có dữ liệu | 0008 → 0007 → 0008 giữ toàn bộ cột/bản ghi của **16 bảng ORM cũ**, gồm session/audit, 2 revision và 3 AI attempts |
| PostgreSQL-only restart | Fingerprint sau restart bằng trước; đọc trước khi chạy lại migrate container |
| Baseline tải riêng | **1.000 hồ sơ**, 5 client × 60 giây, **1.472 request**, **0 lỗi**; chi tiết bên dưới |

[Artifact CI đã làm sạch](https://github.com/Tich-ne1625/HRM-AI-PRO/actions/runs/40109315010/artifacts/12564899906) chứa browser report/ảnh và persistence/HTTP reports; GitHub giữ artifact 14 ngày. Bản [bằng chứng JSON được lưu trong repository](evidence/phase-9-acceptance.json) giữ kết quả định lượng sau khi artifact hết hạn. Không đưa browser profile, cookie, password hay bản ghi thật vào artifacts.

Các số test CI, thao tác browser và request benchmark là các phép đo riêng, không cộng thành một số “test tổng”. Local browser cũng đã đạt bằng Edge 156.0.4314.42; CI dùng source/runtime cuối, local Edge ban đầu dùng image core `d5e7b21`. Baseline tải và 5 lượt race được đo trên backend `d5e7b21`; backend không thay đổi ở `9821e82`.

## Đã triển khai

1. **Ma trận quyền và ledger:** kiểm kê 64 HTTP operations trong [route inventory](phase-9-route-inventory.json), đối chiếu role/resource scope, UUID ngoài quyền, Origin/CSRF, projection/count và atomicity. [Ma trận bảo mật](phase-9-security-matrix.md) nối nhóm route với các regression hiện có; giữ nguyên quyền nghiệp vụ và công thức điểm.
2. **Phiên/cache:** API client dùng session epoch và abort; bỏ response/JSON/refresh đến muộn của phiên cũ. Khi auth/me nhận identity/role/link mới, bỏ query cache và remount form. Các màn hình không render query.data cũ khi query lỗi. Terminal 401/403, kể cả refresh thất bại, kích hoạt kiểm tra lại danh tính; lỗi mạng đơn thuần không tự đăng xuất.
3. **HTTP/login:** body cap thực tế 128 KiB trước xử lý domain; no-store và security headers; web CSP nonce trên HTML động, HSTS theo cấu hình HTTPS production. Limiter PostgreSQL reserve nguyên tử trước Argon2, HMAC email, 10 lượt/300 giây mặc định; 429/Retry-After, lỗi DB 503. Migration `20261024_0008` chỉ thêm `auth_login_limits`; CLI cleanup TTL có giới hạn.
4. **Atomicity/races:** tái chạy refresh/revoke/ADMIN cuối, tổ chức/cycle/KPI/feedback/performance/AI và limiter. Các barrier, timeouts và fault injection kiểm tra rollback/audit/version/revision; không đổi semantics finalization/replay để làm test đạt.
5. **AI isolation:** giữ PUBLIC/HR_PRIVATE, schema validation, lease/fence, lỗi SDK offline và success cũ. Browser chủ động tích xác nhận 3 lượt; provider test trả 2 success rồi quota 503. Không thay runtime bằng một “fake mode”, không gọi Gemini thật trong Phase 9.
6. **Audit reader:** `GET /api/v1/audit-logs`, ADMIN/HR theo allowlist action/entity riêng trước count, snapshot ổn định, DTO 5 trường metadata tối thiểu. Không actor/raw metadata, không quyền HR ngầm cho ADMIN, không endpoint sửa/xóa/export.
7. **E2E/upgrade:** stack, cổng, database, volume và image tag nghiệm thu riêng. Provider giả bind mount từ test source, không có trong runtime image. Workflow có thể chạy lại thủ công và chỉ cleanup project thử nghiệm cố định.
8. **Baseline/bàn giao:** số liệu tải, tài liệu cấu hình/cleanup/audit/giới hạn, CI và dữ liệu demo được đối chiếu. Đã rà soát trực tiếp diff theo threat matrix; không tuyên bố đây là một cuộc pentest hoặc review bảo mật độc lập.

## Luồng browser đã thực hiện

ADMIN tạo HR/MANAGER/EMPLOYEE bằng form. HR tạo phòng/chức danh, liên kết hồ sơ/quản lý, lập/enroll/kích hoạt kỳ, thử đóng sớm nhận 409 và kỳ vẫn ACTIVE; tạo KPI, phân bổ 100% và nhập actual 90. EMPLOYEE và MANAGER gửi SELF/MANAGER rating 4 bằng màn hình xác nhận một lần.

MANAGER tính ra **87.00**, sửa actual xuống 80, báo cáo chuyển **Cần tính lại**, rồi tính lại **80.00**. HR xác nhận chốt; tạo PUBLIC và HR_PRIVATE bằng checkbox/xác nhận; tạo lại PUBLIC nhận quota 503 nhưng nội dung success cũ còn nguyên. HR đóng kỳ và chọn kỳ CLOSED trên dashboard: **average 80.00, sample_size 1**.

HR mở private detail từ danh sách; EMPLOYEE chỉ có 1 PUBLIC result và private UUID trả 404. ADMIN đổi HR thành EMPLOYEE: phiên dùng role mới, private content biến mất và UUID bị chặn. ADMIN tiếp tục vô hiệu hóa tài khoản: phiên cũ về login. Các response chậm/role transition trong cùng cây React còn có deferred-response và AuthProvider tests để kiểm tra cache/form, không chỉ dựa vào reload browser.

## Baseline hiệu năng

Host Windows 11 build 26200, Python 3.12.10, 8 CPU logic; Docker Desktop Engine **29.8.1**, 8 CPU/4.063.952.896 byte RAM được cấp; PostgreSQL **16.15**. Dataset hư cấu: 1.000 nhân viên, 20 phòng, 2 kỳ, 1.998 người-kỳ, 9.990 KPI, 5.994 phản hồi, 1.998 report/revision và 3.996 AI success giả. Một quản lý gốc không đủ quan hệ SELF/MANAGER nên không enroll; đây là lý do có 999 người mỗi kỳ. Audit có 3.008 dòng tại lúc đo, gồm fixture và login setup.

Fixture thu evidence và chấm bằng engine thật: KPI 90, feedback 80, trọng số 70/30 → 87.00; HR sample 999, EMPLOYEE sample 1. Setup/Argon2/login và 11 request warm-up nằm ngoài giai đoạn đo. Dùng **TestClient API trong process + PostgreSQL thật**, 5 client trộn 11 tình huống trong 60 giây; không có build/race nặng đồng thời. Không đo proxy/mạng/trình duyệt và không coi là SLA production.

| Tình huống | Request | p50 ms | p95 ms | Max ms | Max SQL/request |
| --- | ---: | ---: | ---: | ---: | ---: |
| HR dashboard ACTIVE | 133 | 240.95 | 403.18 | 811.53 | 11 |
| HR dashboard CLOSED | 134 | 235.55 | 424.74 | 800.13 | 11 |
| MANAGER dashboard | 135 | 238.52 | 426.06 | 728.12 | 11 |
| EMPLOYEE dashboard | 134 | 202.11 | 369.56 | 557.03 | 11 |
| HR AI trang 1 | 135 | 175.92 | 316.09 | 470.22 | 5 |
| HR AI trang 10 | 135 | 172.33 | 278.03 | 385.70 | 5 |
| HR AI private | 135 | 176.77 | 277.69 | 464.81 | 5 |
| MANAGER AI | 134 | 168.72 | 267.12 | 631.90 | 5 |
| EMPLOYEE AI | 133 | 142.77 | 256.76 | 324.73 | 5 |
| ADMIN audit | 132 | 144.16 | 261.58 | 596.98 | 5 |
| HR audit trang 10 | 132 | 152.30 | 277.19 | 631.96 | 5 |

Scope/count, điểm, page size và audience được assert cùng từng request, không chỉ ghi latency. Dashboard và list có SQL count cố định cho các scope được đo, không thấy N+1 theo mỗi hàng ở baseline này. Không thêm index theo phỏng đoán; workload production hoặc scale lớn hơn cần EXPLAIN/đo lại trước khi chọn index.

## Local và dữ liệu người dùng

Bản local được build/cập nhật qua Compose sau khi cả hai workflow đạt. Không chỉnh `.env`, không nạp lại seed và không gọi Gemini. Fingerprint trước/sau bao phủ tài khoản (id/email/role/active) và toàn bộ cột của organization/cycle/KPI/feedback/report/revision/AI/config: **13 users, 8 employees, 3 cycles, 9 participants, 14 KPI, 19 assignments, 16 feedback, 5 reports, 6 revisions, 3 AI attempts**, cùng 2 phòng, 2 chức danh, 2 định nghĩa KPI, 1 scoring config. Digest chuẩn hóa: `26e60bf40a5fb09f4b2561f671b5f2ae3ca4bab9d82ae785681dd9d995c45cf6`.

Phép kiểm tra demo này không fingerprint password hash, auth sessions hoặc audit; phép roundtrip trên database nghiệm thu riêng kiểm tra toàn bộ cột của các bảng đó. Hai phạm vi được phân biệt để không coi việc đếm demo là bằng chứng bảo toàn toàn database.

## Giới hạn và công đoạn tiếp theo

- Hạn mức theo email chưa chống DDoS, không có MFA/SSO hay ingress rate limit. CSP vẫn cho inline style. Không có cam kết bảo mật tuyệt đối hoặc thu hồi dữ liệu đã tải.
- Benchmark là baseline một máy, tập trung các GET dashboard/AI/audit; chưa phải soak test nhiều giờ, tải ghi hỗn hợp hay hệ thống nhiều node.
- AI fake/SDK transport offline xác nhận tính đúng/privacy/failure handling; chưa nghiệm thu chất lượng tư vấn hoặc toàn bộ PUBLIC/HR_PRIVATE với Gemini thật. Che nhận xét không bảo đảm ẩn danh tuyệt đối.
- API audit đã có, chưa có màn hình audit/export mới. Kubernetes/production hosting chưa được triển khai trong Phase 9.

Công đoạn tiếp theo trong kiến trúc là **Phase 10 — Kubernetes và tài liệu triển khai**. Cần lập hợp đồng/kế hoạch riêng cho manifests, secrets, migration job, probes, ingress/TLS, backup/restore và hướng dẫn vận hành; chưa tự suy diễn rằng đã có môi trường production.

Cách chạy dự án, chỉnh config và chạy lại từng gate nằm trong [hướng dẫn vận hành Phase 9](phase-9-operations.vi.md).
